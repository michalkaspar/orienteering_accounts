import typing, logging
from datetime import datetime, timedelta
from decimal import Decimal
from urllib.parse import urljoin

from django.conf import settings
from django.db import models
from django.db.models import QuerySet
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _

from orienteering_accounts.account.models import Account
from orienteering_accounts.entry.models import Entry
from orienteering_accounts.oris.client import ORISClient
from orienteering_accounts.core.utils import emails as email_utils
from orienteering_accounts.oris import choices as oris_choices
from orienteering_accounts.oris.models import Result

logger = logging.getLogger(__name__)


class Event(models.Model):

    class ProcessingType(models.TextChoices):
        UNPROCESSED = 'UNPROCESSED', _('Nezpracován')
        PAYMENT_INFO_EMAIL_SENT = 'PAYMENT_INFO_EMAIL_SENT', _('Odeslán příkaz k platbě')
        LEADER_EMAIL_SENT = 'LEADER_EMAIL_SENT', _('Odeslán email vedoucímu')
        BILLS_EMAIL_SENT = 'BILLS_EMAIL_SENT', _('Odeslány dluhy vedoucímu')
        BILLS_SOLVED = 'BILLS_SOLVED', _('Dluhy spočteny')

    oris_id = models.PositiveIntegerField(unique=True)
    name = models.CharField(max_length=255, verbose_name=_('Název'))
    date = models.DateField()
    organizer_1 = models.JSONField()
    organizer_2 = models.JSONField(default=dict)
    region = models.CharField(max_length=50)
    discipline = models.JSONField()
    level = models.JSONField()
    ranking = models.DecimalField(decimal_places=2, max_digits=3, default=Decimal('0.0'))
    si_type = models.JSONField(default=dict)
    cancelled = models.BooleanField(default=False)
    gps_lat = models.CharField(max_length=50)
    gps_lon = models.CharField(max_length=50)
    venue = models.CharField(max_length=255, verbose_name=_('Místo'))
    oris_version = models.PositiveSmallIntegerField(null=True, blank=True)
    oris_classes_last_modified_timestamp = models.PositiveIntegerField(null=True, blank=True)
    oris_services_last_modified_timestamp = models.PositiveIntegerField(null=True, blank=True)
    oris_parent_id = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=255, blank=True, default='')
    ob_postupy = models.CharField(max_length=255, blank=True, null=True)
    categories_data = models.JSONField(default=dict)
    entry_date_1 = models.DateTimeField(blank=True, null=True)
    entry_date_2 = models.DateTimeField(blank=True, null=True)
    entry_date_3 = models.DateTimeField(blank=True, null=True)
    entry_bank_account = models.CharField(max_length=255, blank=True, default='')
    links = models.JSONField(default=dict)
    additional_services = models.JSONField(default=dict)
    bills_solved = models.BooleanField(default=False)

    ### Internals
    handled = models.BooleanField(default=False)
    handled_disabled = models.BooleanField(default=False)
    leader = models.ForeignKey(Account, on_delete=models.SET_NULL, blank=True, null=True)
    processing_state = models.CharField(max_length=50, choices=ProcessingType.choices, default=ProcessingType.UNPROCESSED)
    bills_solved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("date",)

    def __str__(self):
        return f'{self.name} {self.date}'

    @property
    def oris_url(self):
        return "https://oris.orientacnisporty.cz/Zavod?id=" + str(self.oris_id)

    @property
    def organizers(self):
        str = f"{self.organizer_1['name']}"
        if self.organizer_2:
            str += f", {self.organizer_2['Name']}"
        return str

    @classmethod
    def import_from_oris(cls):
        for sport in [oris_choices.SPORT_OB, oris_choices.SPORT_MTBO, oris_choices.SPORT_LOB]:
            for event in ORISClient.get_events(sport=sport, include_unofficial_events=1):
                try:
                    instance = cls.objects.get(oris_id=event.oris_id)
                    cls.objects.filter(oris_id=event.oris_id).update(**event.dict(exclude_unset=True))
                    instance.refresh_from_db()
                except cls.DoesNotExist:
                    instance = cls.upsert_from_oris(event)
                if instance.date and instance.date >= timezone.now().date():
                    instance.update_entries()
                    if instance.should_be_handled():
                        instance.handled = True
                        instance.save(update_fields=['handled'])

    @classmethod
    def refresh_from_oris(cls):
        for event in cls.objects.filter(handled=True, processing_state=cls.ProcessingType.UNPROCESSED):
            event._refresh_from_oris()

    @classmethod
    def upsert_from_oris(cls, event):
        instance, _ = cls.objects.update_or_create(
            oris_id=event.oris_id,
            defaults=event.dict()
        )
        instance.refresh_from_db()
        return instance

    @classmethod
    def to_refresh(cls):
        return cls.objects.filter(
            date__gte=datetime.today() - timedelta(days=settings.REFRESH_EVENTS_BEFORE_DAYS)
        )

    def _refresh_from_oris(self):
        oris_event = ORISClient.get_event(self.oris_id)
        self.upsert_from_oris(oris_event)
        self.refresh_from_db()

    @classmethod
    def send_payment_info_emails(cls):
        for event in cls.objects.filter(
            processing_state=cls.ProcessingType.UNPROCESSED,
            handled=True,
            entry_date_1__lte=timezone.now()
        ):
            logger.info(f'Sending payment email for event {event}.')
            event.send_payment_info_email()

    def update_entries(self):
        additional_services = ORISClient.get_event_additional_services(self.oris_id)

        account_ids = set()

        for entry in ORISClient.get_event_entries(self.oris_id):

            entry_additional_services = entry.get_additional_services(additional_services)

            entry = Entry.upsert_from_oris(entry, self, entry_additional_services)
            if entry:
                account_ids.add(entry.account_id)

        self.entries.exclude(account_id__in=account_ids).delete()

    def send_payment_info_email(self):

        event_balance = ORISClient.get_club_event_balance(self.oris_id)

        if not event_balance:
            return

        context = {
            'event_balance': event_balance,
            'event': self,
            'club_id': settings.CLUB_ID
        }

        html_content = render_to_string('emails/event_payment_info.html', context)

        email_utils.send_email(
            recipient_list=settings.EVENT_PAYMENT_EMAILS_SEND_TO,
            subject=f'{self.date.strftime("%d.%m.%Y")} {self.oris_id} {self.name} - platba',
            html_content=html_content
        )

        self.processing_state = Event.ProcessingType.PAYMENT_INFO_EMAIL_SENT
        self.save(update_fields=['processing_state'])

    @classmethod
    def send_leader_debts_emails(cls):
        for event in cls.objects.filter(
            processing_state=cls.ProcessingType.LEADER_EMAIL_SENT,
            leader__isnull=False,
            handled=True,
            date__lt=timezone.now().date()
        ):
            logger.info(f'Sending debts email to leader for event {event}.')
            event.send_leader_debts_email()

    def send_leader_debts_email(self):

        assert self.processing_state == Event.ProcessingType.LEADER_EMAIL_SENT and self.leader

        context = {
            'event': self,
            'bills_url': f'http://{settings.PROJECT_DOMAIN}{reverse("events:bills", args=[self.pk, self.leader.leader_key])}'
        }

        html_content = render_to_string('emails/event_debts.html', context)

        email_utils.send_email(
            recipient_list=[self.leader.email],
            subject=f'{self.date.strftime("%d.%m.%Y")} {self.name} - dluhy',
            html_content=html_content
        )

        self.processing_state = Event.ProcessingType.BILLS_EMAIL_SENT
        self.save(update_fields=['processing_state'])

    @classmethod
    def send_leader_entries_emails(cls):
        for event in cls.objects.filter(
            processing_state=cls.ProcessingType.PAYMENT_INFO_EMAIL_SENT,
            leader__isnull=False,
            handled=True,
            entry_date_1__lte=timezone.now(),
            entries__isnull=False
        ).distinct():
            logger.info(f'Sending entries email to leader for event {event}.')
            event.send_leader_entries_email()

    def send_leader_entries_email(self):

        assert self.entries.exists() and self.leader

        context = {
            'event': self,
            'entries_url': f'http://{settings.PROJECT_DOMAIN}{reverse("events:entries_preview", args=[self.pk, self.leader.leader_key])}'
        }

        html_content = render_to_string('emails/event_entries.html', context)

        email_utils.send_email(
            recipient_list=[self.leader.email],
            subject=f'{self.date.strftime("%d.%m.%Y")} {self.name} - přihlášky',
            html_content=html_content
        )

        self.processing_state = Event.ProcessingType.LEADER_EMAIL_SENT
        self.save(update_fields=['processing_state'])

    def get_category_fee(self, category_name: str) -> Decimal:
        for _, category_dict in self.categories_data.items():
            if category_dict.get('Name') == category_name:
                return Decimal(category_dict.get('Fee', 0))
        return Decimal(0)

    @property
    def is_stage(self):
        return True if self.discipline and self.discipline.get('oris_id') == settings.ORIS_STAGE_RACE_ID else False

    @property
    def is_relay(self):
        return True if self.discipline and self.discipline.get('oris_id') in settings.ORIS_RELAY_RACE_IDS else False

    @cached_property
    def results(self) -> typing.Dict[str, Result]:
        return ORISClient.get_event_results(self.oris_id)

    def did_not_start(self, registration_number: str) -> bool:
        result = self.results.get(registration_number)

        if not result:
            return True

        if result.time == 'DNS':
            return True

        return False

    def should_be_handled(self) -> bool:
        if self.handled or self.handled_disabled:
            return False

        if self.is_relay:
            return ORISClient.club_entry_exists(self.oris_id)

        return self.entries.exists()

from datetime import datetime, timedelta
from decimal import Decimal
from urllib.parse import urljoin

from django.conf import settings
from django.db import models
from django.db.models import QuerySet
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _

from orienteering_accounts.account.models import Account
from orienteering_accounts.entry.models import Entry
from orienteering_accounts.oris.client import ORISClient
from orienteering_accounts.core.utils import emails as email_utils


class Event(models.Model):
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
    leader = models.ForeignKey(Account, on_delete=models.SET_NULL, blank=True, null=True)

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
            str += f", {self.organizer_2['name']}"
        return str

    @classmethod
    def upsert_from_oris(cls, event):
        cls.objects.update_or_create(
            oris_id=event.oris_id,
            defaults=event.dict()
        )

    @classmethod
    def to_refresh(cls):
        return cls.objects.filter(
            date__gte=datetime.today() - timedelta(days=settings.REFRESH_EVENTS_BEFORE_DAYS)
        )

    def update_entries(self):
        additional_services = ORISClient.get_event_additional_services(self.oris_id)

        for entry in ORISClient.get_event_entries(self.oris_id):
            Entry.upsert_from_oris(entry, self, additional_services.get(entry.oris_user_id, {}))

    @classmethod
    def to_send_payment_info_email(cls) -> QuerySet:
        return cls.objects.filter(
            handled=True,
            entry_date_1__isnull=False,
            entry_date_1__lte=timezone.now()
        ).exclude(
            entry_bank_account=''
        )

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
            subject=f'{self.date.strftime("%d.%m.%Y")} {self.name} - platba',
            html_content=html_content
        )

    def send_leader_debts_email(self):

        if self.bills_solved:
            return

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
from datetime import datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import QuerySet
from django.template.loader import render_to_string
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

    ### Internals
    handled = models.BooleanField(default=False)
    leader = models.ForeignKey(Account, on_delete=models.SET_NULL, blank=True, null=True)

    class Meta:
        ordering = ("date",)

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
        for entry in ORISClient.get_event_entries(self.oris_id):
            Entry.upsert_from_oris(entry, self)

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

        club_event_balance = ORISClient.get_club_event_balance(self.oris_id)

        if not club_event_balance:
            return

        context = {
            'payment_amount': club_event_balance,
            'account_number': self.entry_bank_account
        }

        html_content = render_to_string('emails/event_payment_info.html', context)

        email_utils.send_email(
            recipient_list=settings.EVENT_PAYMENT_EMAILS_SEND_TO,
            subject=f'{self.name} - platba',
            html_content=html_content
        )

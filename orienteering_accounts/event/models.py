from datetime import datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils.translation import ugettext_lazy as _

from orienteering_accounts.entry.models import Entry
from orienteering_accounts.oris.client import ORISClient


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
            Entry.upsert_from_oris(**entry)

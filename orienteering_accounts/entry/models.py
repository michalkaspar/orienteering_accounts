import logging
from datetime import datetime
from decimal import Decimal

from django.db import models

from orienteering_accounts.account.models import Account

logger = logging.getLogger(__name__)


class Entry(models.Model):
    oris_id = models.PositiveIntegerField(unique=True)
    oris_category_id = models.PositiveIntegerField()
    category_name = models.CharField(max_length=255, blank=True, default='')
    account = models.ForeignKey('account.Account', related_name='entries', on_delete=models.CASCADE)
    event = models.ForeignKey('event.Event', related_name='entries', on_delete=models.CASCADE)
    fee = models.PositiveIntegerField()
    oris_created = models.DateTimeField(null=True, blank=True)
    oris_updated = models.DateTimeField(null=True, blank=True)
    rent_si = models.BooleanField(default=False)
    additional_services = models.JSONField(default={})
    debt = models.DecimalField(decimal_places=2, max_digits=9, null=True)

    @classmethod
    def upsert_from_oris(cls, entry, event: 'Event', additional_services: dict = {}):
        if not entry.oris_user_id:
            return

        try:
            account = Account.objects.get(oris_id=entry.oris_user_id)
        except Account.DoesNotExist:
            logger.error(f'Entry for event {event} not created, account ORIS ID {entry.account_oris_id} does not exists.')
            return

        cls.objects.update_or_create(
            account_id=account.pk,
            event_id=event.pk,
            defaults={
                'additional_services': additional_services,
                **entry.dict(exclude={'oris_user_id'})
            }
        )

    @property
    def fee_after_club_discount(self):
        current_year = datetime.now().year
        born_year = self.account.born_year + 2000 if self.account.born_year < current_year - 2000 else self.account.born_year + 1900
        if current_year - born_year > 20:
            return self.fee / Decimal(2)
        return Decimal(0)

    @property
    def debt_init(self):
        additional_services_cost_sum = Decimal(0)

        for _, service in self.additional_services.items():
            additional_services_cost_sum += Decimal(service['TotalFee'])

        # FIXME solve late entries properly

        return self.fee_after_club_discount + additional_services_cost_sum

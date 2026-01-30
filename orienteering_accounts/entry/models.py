import logging
import typing
from datetime import datetime
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from orienteering_accounts.account.models import Account, Transaction
from orienteering_accounts.oris.models import BaseEntry

logger = logging.getLogger(__name__)


class Entry(models.Model):
    oris_id = models.PositiveIntegerField(unique=True, null=True)
    oris_category_id = models.PositiveIntegerField()
    category_name = models.CharField(max_length=255, blank=True, default='')
    account = models.ForeignKey('account.Account', related_name='entries', on_delete=models.CASCADE)
    event = models.ForeignKey('event.Event', related_name='entries', on_delete=models.CASCADE)
    fee = models.PositiveIntegerField(default=0)
    oris_created = models.DateTimeField(null=True, blank=True)
    oris_updated = models.DateTimeField(null=True, blank=True)
    rent_si = models.BooleanField(default=False)
    additional_services = models.JSONField(default={})
    debt = models.DecimalField(decimal_places=2, max_digits=9, null=True, validators=(MinValueValidator(0),))
    other_debt = models.DecimalField(decimal_places=2, max_digits=9, null=True, validators=(MinValueValidator(0),))
    debt_note = models.CharField(max_length=255, null=True, blank=True)
    oris_club_note = models.TextField(blank=True, null=True)

    def __str__(self):
        return f'{self.event} entry {self.account}'

    @classmethod
    def upsert_from_oris(cls, entry: BaseEntry, event: 'Event', additional_services: list = None) -> typing.Optional['Entry']:
        if not entry.is_valid:
            return

        try:
            account = Account.objects.get(**entry.account_kwargs)
        except Account.DoesNotExist:
            logger.warning(f'Entry for event {event} not created, account ORIS ID {entry.account_kwargs} does not exists.')
            return

        instance, created = cls.objects.update_or_create(
            account_id=account.pk,
            event_id=event.pk,
            defaults={
                'additional_services': additional_services,
                **entry.dict(exclude={'oris_user_id', 'registration_number'})
            }
        )

        if created:
            if instance.fee_after_club_discount != 0:
                instance.transactions.create(
                    account=account,
                    amount=-instance.fee_after_club_discount,
                    purpose=Transaction.TransactionPurpose.ENTRY,
                    author_name="System",
                    is_future=True
                )

            if additional_services:
                for service in additional_services:
                    instance.transactions.create(
                        account=account,
                        amount=-Decimal(service['TotalFee']),
                        purpose=Transaction.TransactionPurpose.ENTRY_OTHER,
                        author_name="System",
                        note=service['Service']['NameCZ'],
                        is_future=True
                    )


        return instance

    @property
    def fee_after_club_discount(self):
        category_entry_fee = self.event.get_category_fee(self.category_name)

        if self.event.is_relay:
            fee = Decimal(0)
        elif self.event.is_multi_stage or self.event.is_stage or self.event.did_not_start(self.account.registration_number):
            # In case of stage event or runner
            fee = category_entry_fee
        else:
            if self.account.is_adult:
                fee = category_entry_fee / Decimal(2)
            else:
                fee = Decimal(0)

        if not self.event.is_relay:
            late_entry_fee = self.fee - category_entry_fee
            fee += late_entry_fee

        return fee

    @property
    def additional_services_cost_sum(self) -> Decimal:
        additional_services_cost_sum = Decimal(0)

        self.additional_services: list

        if self.additional_services:
            for service in self.additional_services:
                additional_services_cost_sum += Decimal(service['TotalFee'])

        return additional_services_cost_sum

    @property
    def debt_init(self):
        return self.fee_after_club_discount + self.additional_services_cost_sum

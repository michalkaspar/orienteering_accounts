import logging

from django.db import models

from orienteering_accounts.account.models import Account

logger = logging.getLogger(__name__)


class Entry(models.Model):
    oris_id = models.PositiveIntegerField(unique=True)
    oris_category_id = models.PositiveIntegerField()
    account = models.ForeignKey('account.Account', related_name='entries', on_delete=models.CASCADE)
    event = models.ForeignKey('event.Event', related_name='entries', on_delete=models.CASCADE)
    fee = models.PositiveIntegerField()
    oris_created = models.DateTimeField(null=True, blank=True)
    oris_updated = models.DateTimeField(null=True, blank=True)
    rent_si = models.BooleanField(default=False)

    @classmethod
    def upsert_from_oris(cls, entry, event: 'Event'):
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
            defaults=entry.dict(exclude={'oris_user_id'})
        )

import logging
from datetime import timedelta

from django.conf import settings
from django.core.management import BaseCommand
from django.core.cache import cache
from django.utils import timezone
from django.db import transaction

from orienteering_accounts.account.models import Account, PaymentPeriod
from orienteering_accounts.rb.client import RBBankAPIClient

logger = logging.getLogger(__name__)


class Command(BaseCommand):

    def handle(self, **options):
        logger.info(f'Processing of bank transactions from RB API started')

        last_read_timestamp_cache_key = settings.LAST_BANK_TRANSACTION_READ_CACHE_KEY_PATTERN.format(
            bank_account_number=settings.CLUB_BANK_ACCOUNT_NUMBER
        )

        last_read_timestamp = cache.get(last_read_timestamp_cache_key) or timezone.now() - timedelta(hours=6)
        current_timestamp = timezone.now()
        payment_period = PaymentPeriod.get_last_period()

        bank_transactions = RBBankAPIClient.get_transactions(from_date=last_read_timestamp, to_date=current_timestamp)

        with transaction.atomic():
            for bank_transaction in reversed(bank_transactions):
                logger.info(f'Processing bank transaction {bank_transaction.dict()}')
                Account.process_bank_transaction(bank_transaction, payment_period)

        cache.set(last_read_timestamp_cache_key, current_timestamp)

        logger.info(f'Processing of bank transactions from RB API finished')

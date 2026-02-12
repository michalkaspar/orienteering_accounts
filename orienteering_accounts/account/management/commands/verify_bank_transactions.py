import logging
from datetime import timedelta

from django.core.management import BaseCommand
from django.utils import timezone

from orienteering_accounts.account.models import BankTransaction, PaymentPeriod
from orienteering_accounts.account.services import process_bank_transactions_batch
from orienteering_accounts.rb.client import RBBankAPIClient

logger = logging.getLogger(__name__)


class Command(BaseCommand):

    def handle(self, **options):
        logger.info('Verification of bank transactions from RB API started')

        to_date = timezone.now()
        from_date = to_date - timedelta(days=1)
        payment_period = PaymentPeriod.get_last_period()

        bank_transactions = RBBankAPIClient.get_transactions(from_date=from_date, to_date=to_date)

        api_remote_ids = {bt.entryReference for bt in bank_transactions}
        existing_ids = set(
            BankTransaction.objects.filter(remote_id__in=api_remote_ids).values_list('remote_id', flat=True)
        )
        missing_ids = api_remote_ids - existing_ids

        missing_transactions = [bt for bt in bank_transactions if bt.entryReference in missing_ids]

        if missing_transactions:
            process_bank_transactions_batch(missing_transactions, payment_period)
            logger.info(
                f'Verification finished: found {len(bank_transactions)} transactions, '
                f'{len(existing_ids)} already imported, {len(missing_transactions)} reimported'
            )
        else:
            logger.info(
                f'Verification finished: found {len(bank_transactions)} transactions, '
                f'all already imported'
            )

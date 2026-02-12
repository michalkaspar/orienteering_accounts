import logging

from django.db import transaction

from orienteering_accounts.account.models import Account

logger = logging.getLogger(__name__)


def process_bank_transactions_batch(bank_transactions, payment_period):
    """Process a batch of bank transactions. Each transaction in try/except."""
    for bank_transaction in reversed(bank_transactions):
        logger.info(f'Processing bank transaction {bank_transaction.dict()}')
        try:
            with transaction.atomic():
                Account.process_bank_transaction(bank_transaction, payment_period)
        except Exception:
            logger.exception(
                f'Error processing bank transaction',
                extra={'transaction_data': bank_transaction.dict()}
            )

import logging

from django.conf import settings
from django.db import transaction

from orienteering_accounts.account.models import Account
from orienteering_accounts.oris import choices as oris_choices
from orienteering_accounts.oris.client import ORISClient

logger = logging.getLogger(__name__)


def _get_oris_registered_numbers() -> set:
    """Fetch registered user registration numbers from ORIS for the current year (OB + MTBO)."""
    try:
        registered_ob = ORISClient.get_registered_users(
            sport=oris_choices.SPORT_OB, club_id=settings.CLUB_ID
        )
        registered_mtbo = ORISClient.get_registered_users(
            sport=oris_choices.SPORT_MTBO, club_id=settings.CLUB_ID
        )
        return {user.registration_number for user in registered_ob + registered_mtbo}
    except Exception:
        logger.exception("Failed to fetch registered users from ORIS")
        return set()


def process_bank_transactions_batch(bank_transactions, payment_period):
    """Process a batch of bank transactions. Each transaction in try/except."""
    oris_registered_numbers = _get_oris_registered_numbers()

    for bank_transaction in reversed(bank_transactions):
        logger.info(f"Processing bank transaction {bank_transaction.dict()}")
        try:
            with transaction.atomic():
                Account.process_bank_transaction(
                    bank_transaction, payment_period, oris_registered_numbers
                )
        except Exception:
            logger.exception(
                f"Error processing bank transaction",
                extra={"transaction_data": bank_transaction.dict()},
            )

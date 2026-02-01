import logging
from decimal import Decimal
from django.conf import settings
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from orienteering_accounts.account.models import Transaction

logger = logging.getLogger(__name__)


_account_old_balance = {}


@receiver(pre_save, sender=Transaction)
def store_old_account_balance(sender, instance, **kwargs):
    _account_old_balance[instance.account_id] = instance.account.balance


def check_balance(account):
    """
    Helper function to check balance and send negative balance email if needed.
    
    Note: This email is NOT sent when the balance reaches the maximum negative
    threshold, as the entry rights removed email will be sent instead.
    """
    balance = account.balance
    old_balance = _account_old_balance[account.id]
    maximum_threshold = Decimal(str(settings.MAXIMUM_NEGATIVE_BALANCE))
    
    if balance > maximum_threshold:

        if old_balance <= maximum_threshold:
            # Balance was previously at or below max threshold, add back entry rights
            account.add_entry_rights_in_oris()
            logger.info(
                f'ORIS entry rights restored for {account.full_name} '
                f'({account.registration_number}). Balance: {balance}'
            )
            return

        if balance < Decimal(0) and balance < old_balance:
            # Balance is negative and decreased, send negative balance email
            try:
                account.send_debts_payment_info_email()
                logger.info(
                    f'Negative balance email sent to {account.full_name} '
                    f'({account.registration_number}). Balance: {balance}'
                )
            except Exception as e:
                logger.error(
                    f'Failed to send negative balance email to {account.full_name} '
                    f'({account.registration_number}): {str(e)}'
                )
    elif old_balance > maximum_threshold:
        # Balance is at or below maximum threshold, remove entry rights
        try:
            # Remove entry rights in ORIS
            if account.oris_club_member_id:
                account.remove_entry_rights_in_oris()
                logger.info(
                    f'ORIS entry rights removed for {account.full_name} '
                    f'({account.registration_number}). Balance: {balance}'
                )

            # Send notification email
            account.send_entry_rights_removed_info_email()
            logger.info(
                f'Entry rights removed email sent to {account.full_name} '
                f'({account.registration_number}). Balance: {balance}'
            )

        except Exception as e:
            logger.error(
                f'Failed to remove entry rights for {account.full_name} '
                f'({account.registration_number}): {str(e)}'
            )


@receiver(post_save, sender=Transaction)
def handle_transaction_save(sender, instance, created, **kwargs):
    """
    Handle transaction creation or update.
    Check balance and trigger appropriate actions when:
    - A new transaction is created
    - An existing transaction's amount is changed
    """
    account = instance.account

    if instance.amount and instance.amount > Decimal(0) and not instance.is_club_membership:
        check_balance(account)


@receiver(post_delete, sender=Transaction)
def handle_transaction_delete(sender, instance, **kwargs):
    """
    Handle transaction deletion.
    Check balance and trigger appropriate actions when a transaction is deleted.
    """
    account = instance.account
    if not instance.is_club_membership:
        check_balance(account)

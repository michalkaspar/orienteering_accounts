import logging
from decimal import Decimal
from django.conf import settings
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from orienteering_accounts.account.models import Transaction

logger = logging.getLogger(__name__)

# Store the old amount before update to detect changes
_transaction_old_amount = {}


@receiver(pre_save, sender=Transaction)
def store_old_transaction_amount(sender, instance, **kwargs):
    """
    Store the old amount before a transaction is updated.
    This allows us to detect if the amount changed.
    """
    if instance.pk:
        try:
            old_transaction = Transaction.objects.get(pk=instance.pk)
            _transaction_old_amount[instance.pk] = old_transaction.amount
        except Transaction.DoesNotExist:
            pass


def check_and_send_negative_balance_email(account):
    """
    Helper function to check balance and send negative balance email if needed.
    
    Note: This email is NOT sent when the balance reaches the maximum negative
    threshold, as the entry rights removed email will be sent instead.
    """
    balance = account.balance
    maximum_threshold = Decimal(str(settings.MAXIMUM_NEGATIVE_BALANCE))
    
    # Check if balance is negative but NOT at or below the maximum threshold
    # (to avoid sending both emails)
    if 0 > balance > maximum_threshold:
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


def check_and_remove_entry_rights(account):
    """
    Helper function to check balance and remove entry rights if threshold is reached.
    
    Remove ORIS entry rights and Google Workspace access when account balance
    reaches or falls below the maximum negative balance threshold (from settings).
    Also sends notification email to the user.
    """
    balance = account.balance
    maximum_threshold = Decimal(str(settings.MAXIMUM_NEGATIVE_BALANCE))
    
    # Check if balance has crossed the maximum negative threshold
    # and entry rights haven't been removed yet
    if balance <= maximum_threshold and not account.is_late_with_club_membership_payment:
        try:
            # Remove entry rights in ORIS
            if account.oris_club_member_id:
                account.remove_entry_rights_in_oris()
                logger.info(
                    f'ORIS entry rights removed for {account.full_name} '
                    f'({account.registration_number}). Balance: {balance}'
                )
            
            # Mark account as late with payment
            account.is_late_with_club_membership_payment = True
            account.save(update_fields=['is_late_with_club_membership_payment'])
            
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
    amount_changed = False

    if instance.amount and instance.mount > Decimal(0):
        # Positive amount transactions do not affect debt checks
        if account.balance >= Decimal(0) and account.is_late_with_club_membership_payment:
            # If balance is now non-negative, reset late payment status
            account.is_late_with_club_membership_payment = False
            account.add_entry_rights_in_oris()
            account.save(update_fields=['is_late_with_club_membership_payment'])

    if not created and instance.pk in _transaction_old_amount:
        # Transaction was updated - check if amount changed
        old_amount = _transaction_old_amount.pop(instance.pk)
        amount_changed = old_amount != instance.amount
    
    # Only proceed if transaction was created or amount changed
    if created or amount_changed:
        check_and_send_negative_balance_email(account)
        check_and_remove_entry_rights(account)


@receiver(post_delete, sender=Transaction)
def handle_transaction_delete(sender, instance, **kwargs):
    """
    Handle transaction deletion.
    Check balance and trigger appropriate actions when a transaction is deleted.
    """
    account = instance.account
    
    # Clean up stored old amount if it exists
    if instance.pk in _transaction_old_amount:
        _transaction_old_amount.pop(instance.pk)
    
    # Check balance after deletion
    check_and_send_negative_balance_email(account)
    check_and_remove_entry_rights(account)

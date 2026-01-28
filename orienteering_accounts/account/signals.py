import logging
from decimal import Decimal
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from orienteering_accounts.account.models import Transaction

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Transaction)
def send_negative_balance_email(sender, instance, created, **kwargs):
    """
    Send email notification when a new transaction is created
    and the account balance becomes negative.
    
    Note: This email is NOT sent when the balance reaches the maximum negative
    threshold, as the entry rights removed email will be sent instead.
    """
    if created:
        account = instance.account
        balance = account.balance
        maximum_threshold = Decimal(str(settings.MAXIMUM_NEGATIVE_BALANCE))
        
        # Check if balance is negative but NOT at or below the maximum threshold
        # (to avoid sending both emails)
        if balance < 0 and balance > maximum_threshold:
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


@receiver(post_save, sender=Transaction)
def remove_entry_rights_on_maximum_debt(sender, instance, created, **kwargs):
    """
    Remove ORIS entry rights and Google Workspace access when account balance
    reaches or falls below the maximum negative balance threshold (from settings).
    Also sends notification email to the user.
    """
    if created:
        account = instance.account
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
                
                # Remove from Google Workspace
                if account.email and not account.removed_from_google_workspace:
                    account.remove_from_google_workspace_group()
                    logger.info(
                        f'Removed from Google Workspace: {account.full_name} '
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

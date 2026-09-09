import logging
from decimal import Decimal
from functools import partial

from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_save, post_delete, pre_save, pre_delete
from django.dispatch import receiver

from orienteering_accounts.account.models import Account, Transaction

logger = logging.getLogger(__name__)


# account_id -> balance before the FIRST Transaction change for that account
# in the current DB transaction. Popped by the on_commit callback, which both
# deduplicates checks (one per account per commit) and cleans the dict up.
# An entry left behind by a rollback still holds the correct pre-change
# balance and is reused (via setdefault) and popped by the next commit.
# Shared module-level state: same thread-safety exposure as the previous
# implementation (fine with sync workers).
_pending_balance_checks = {}


@receiver(pre_save, sender=Transaction)
def store_old_account_balance(sender, instance, **kwargs):
    if instance.is_club_membership:
        return
    _pending_balance_checks.setdefault(instance.account_id, instance.account.balance)


@receiver(pre_delete, sender=Transaction)
def store_old_account_balance_on_delete(sender, instance, **kwargs):
    if instance.is_club_membership:
        return
    _pending_balance_checks.setdefault(instance.account_id, instance.account.balance)


def _run_balance_check(account_id):
    old_balance = _pending_balance_checks.pop(account_id, None)
    if old_balance is None:
        # Balance already checked for this account in this commit.
        return
    account = Account.objects.filter(pk=account_id).first()
    if account is None:
        # Account deleted before commit (e.g. cascade delete).
        return
    check_balance(account, old_balance)


def check_balance(account, old_balance):
    """
    Helper function to check balance and send negative balance email if needed.
    
    Note: This email is NOT sent when the balance reaches the maximum negative
    threshold, as the entry rights removed email will be sent instead.
    """
    balance = account.balance
    maximum_threshold = Decimal(str(settings.MAXIMUM_NEGATIVE_BALANCE))
    
    if balance > maximum_threshold:
        account.add_entry_rights_in_oris()

        if old_balance <= maximum_threshold:
            # Balance was previously at or below max threshold, add back entry rights
            try:
                logger.info(
                    f'ORIS entry rights restored for {account.full_name} '
                    f'({account.registration_number}). Balance: {balance}'
                )
                
                # Send unblock notification email
                account.send_entry_rights_restored_info_email()
                logger.info(
                    f'Entry rights restored email sent to {account.full_name} '
                    f'({account.registration_number}). Balance: {balance}'
                )
            except Exception as e:
                logger.error(
                    f'Failed to restore entry rights for {account.full_name} '
                    f'({account.registration_number}): {str(e)}'
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


def _restore_entry_rights_after_club_membership(account_id):
    account = Account.objects.filter(pk=account_id).first()
    if account is None or not account.is_late_with_club_membership_payment:
        # Account deleted before commit, or the flag was already cleared by
        # an earlier callback in this commit.
        return
    try:
        account.add_entry_rights_in_oris()
        account.is_late_with_club_membership_payment = False
        account.save(update_fields=['is_late_with_club_membership_payment'])
        account.send_entry_rights_restored_info_email()
        logger.info(
            f'ORIS entry rights restored for {account.full_name} '
            f'({account.registration_number}) after club membership payment.'
        )
    except Exception as e:
        logger.error(
            f'Failed to restore entry rights for {account.full_name} '
            f'({account.registration_number}): {str(e)}'
        )


@receiver(post_save, sender=Transaction)
def handle_transaction_save(sender, instance, created, **kwargs):
    """
    Handle transaction creation or update.
    Check balance and trigger appropriate actions when:
    - A new transaction is created
    - An existing transaction's amount is changed

    Club membership transactions are excluded from the balance check
    (they don't affect Account.balance) but instead restore ORIS entry
    rights if the account was marked late on club membership payment.

    All side effects (ORIS calls, emails) run after the current DB
    transaction commits, and are discarded on rollback.
    """
    account = instance.account

    if instance.is_club_membership:
        if account.is_late_with_club_membership_payment:
            transaction.on_commit(
                partial(_restore_entry_rights_after_club_membership, instance.account_id)
            )
        return

    if instance.amount and instance.amount != Decimal(0):
        transaction.on_commit(partial(_run_balance_check, instance.account_id))


@receiver(post_delete, sender=Transaction)
def handle_transaction_delete(sender, instance, **kwargs):
    """
    Handle transaction deletion.
    Check balance and trigger appropriate actions when a transaction is deleted.
    """
    if not instance.is_club_membership:
        transaction.on_commit(partial(_run_balance_check, instance.account_id))

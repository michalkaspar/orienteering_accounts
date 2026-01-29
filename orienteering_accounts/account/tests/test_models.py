from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from model_bakery import baker

from freezegun import freeze_time


from orienteering_accounts.account.models import Transaction, Account


class AccountTestCase(TestCase):

    def test_get_accounts_without_paid_club_membership(self):
        account1 = baker.make('account.Account')
        account2 = baker.make('account.Account')
        account3 = baker.make('account.Account')

        baker.make('account.Transaction', account=account1, purpose=Transaction.TransactionPurpose.CLUB_MEMBERSHIP, amount=Decimal('1'))
        with freeze_time(timezone.now() - timedelta(days=400)):
            baker.make('account.Transaction', account=account2, purpose=Transaction.TransactionPurpose.CLUB_MEMBERSHIP, amount=Decimal('1'))
        baker.make('account.Transaction', account=account3, purpose=Transaction.TransactionPurpose.OTHER, amount=Decimal('1'))

        system_settings = baker.make('core.Settings', club_membership_deadline=timezone.now())

        accounts_without_paid_club_memberships = Account.get_accounts_without_paid_club_membership(system_settings.club_membership_deadline)

        self.assertEqual(accounts_without_paid_club_memberships.count(), 2)
        self.assertCountEqual([account2.pk, account3.pk], accounts_without_paid_club_memberships.values_list('pk', flat=True))


class TransactionSignalTestCase(TestCase):

    @patch('orienteering_accounts.account.models.Account.send_debts_payment_info_email')
    def test_negative_balance_email_sent_on_new_transaction(self, mock_send_email):
        """Test that email is sent when a new transaction creates negative balance (above max threshold)"""
        # Create account with zero initial balance
        account = baker.make('account.Account', init_balance=Decimal('0'), email='test@example.com')
        
        # Create a negative transaction that's above the -2000 threshold
        baker.make(
            'account.Transaction',
            account=account,
            amount=Decimal('-100'),
            purpose=Transaction.TransactionPurpose.ENTRY
        )
        
        # Verify email was sent
        mock_send_email.assert_called_once()

    @patch('orienteering_accounts.account.models.Account.send_debts_payment_info_email')
    def test_negative_balance_email_not_sent_when_balance_positive(self, mock_send_email):
        """Test that email is NOT sent when balance remains positive"""
        # Create account with positive initial balance
        account = baker.make('account.Account', init_balance=Decimal('1000'), email='test@example.com')
        
        # Create a negative transaction that doesn't make balance negative
        baker.make(
            'account.Transaction',
            account=account,
            amount=Decimal('-100'),
            purpose=Transaction.TransactionPurpose.ENTRY
        )
        
        # Verify email was NOT sent
        mock_send_email.assert_not_called()

    @patch('orienteering_accounts.account.models.Account.send_debts_payment_info_email')
    def test_negative_balance_email_not_sent_on_non_amount_update(self, mock_send_email):
        """Test that email is NOT sent when a transaction is updated but amount doesn't change"""
        # Create account with negative balance
        account = baker.make('account.Account', init_balance=Decimal('0'), email='test@example.com')
        
        # Create a negative transaction
        transaction = baker.make(
            'account.Transaction',
            account=account,
            amount=Decimal('-100'),
            purpose=Transaction.TransactionPurpose.ENTRY
        )
        
        # Reset the mock
        mock_send_email.reset_mock()
        
        # Update the transaction (but not the amount)
        transaction.note = "Updated note"
        transaction.save()
        
        # Verify email was NOT sent again on update
        mock_send_email.assert_not_called()

    @patch('orienteering_accounts.account.models.Account.send_debts_payment_info_email')
    def test_negative_balance_email_sent_on_amount_update(self, mock_send_email):
        """Test that email IS sent when a transaction amount is updated causing negative balance"""
        # Create account with positive balance
        account = baker.make('account.Account', init_balance=Decimal('100'), email='test@example.com')
        
        # Create a small negative transaction (balance still positive)
        transaction = baker.make(
            'account.Transaction',
            account=account,
            amount=Decimal('-50'),
            purpose=Transaction.TransactionPurpose.ENTRY
        )
        
        # Reset the mock (no email sent yet as balance is still positive)
        mock_send_email.reset_mock()
        
        # Update the transaction amount to make balance negative
        transaction.amount = Decimal('-200')
        transaction.save()
        
        # Verify email was sent after amount update
        mock_send_email.assert_called_once()

    @patch('orienteering_accounts.account.models.Account.send_debts_payment_info_email')
    def test_negative_balance_email_sent_on_transaction_deletion(self, mock_send_email):
        """Test that email IS sent when a transaction is deleted and balance becomes negative"""
        # Create account with positive balance due to positive transaction
        account = baker.make('account.Account', init_balance=Decimal('-100'), email='test@example.com')
        
        # Create a positive transaction (balance becomes 0)
        transaction = baker.make(
            'account.Transaction',
            account=account,
            amount=Decimal('100'),
            purpose=Transaction.TransactionPurpose.DEBTS
        )
        
        # Reset the mock
        mock_send_email.reset_mock()
        
        # Delete the transaction (balance becomes -100 again)
        transaction.delete()
        
        # Verify email was sent after deletion
        mock_send_email.assert_called_once()

    @patch('orienteering_accounts.account.models.Account.send_debts_payment_info_email')
    def test_negative_balance_email_sent_when_balance_becomes_negative(self, mock_send_email):
        """Test that email is sent when balance transitions from positive to negative (above max threshold)"""
        # Create account with small positive balance
        account = baker.make('account.Account', init_balance=Decimal('50'), email='test@example.com')
        
        # Create a negative transaction that makes balance negative but above -2000 threshold
        baker.make(
            'account.Transaction',
            account=account,
            amount=Decimal('-100'),
            purpose=Transaction.TransactionPurpose.ENTRY
        )
        
        # Verify email was sent
        mock_send_email.assert_called_once()

    @patch('orienteering_accounts.account.models.Account.send_debts_payment_info_email')
    def test_negative_balance_email_not_sent_at_maximum_threshold(self, mock_send_email):
        """Test that negative balance email is NOT sent when balance reaches -2000 (entry rights email sent instead)"""
        # Create account with zero balance
        account = baker.make('account.Account', init_balance=Decimal('0'), email='test@example.com')
        
        # Create a transaction that makes balance exactly -2000
        baker.make(
            'account.Transaction',
            account=account,
            amount=Decimal('-2000'),
            purpose=Transaction.TransactionPurpose.ENTRY
        )
        
        # Verify negative balance email was NOT sent (entry rights email will be sent instead)
        mock_send_email.assert_not_called()

    @patch('orienteering_accounts.account.models.Account.send_debts_payment_info_email')
    def test_negative_balance_email_not_sent_below_maximum_threshold(self, mock_send_email):
        """Test that negative balance email is NOT sent when balance is below -2000"""
        # Create account with zero balance
        account = baker.make('account.Account', init_balance=Decimal('0'), email='test@example.com')
        
        # Create a transaction that makes balance below -2000
        baker.make(
            'account.Transaction',
            account=account,
            amount=Decimal('-2500'),
            purpose=Transaction.TransactionPurpose.ENTRY
        )
        
        # Verify negative balance email was NOT sent
        mock_send_email.assert_not_called()


class EntryRightsRemovalSignalTestCase(TestCase):

    @patch('orienteering_accounts.account.models.Account.send_entry_rights_removed_info_email')
    @patch('orienteering_accounts.account.models.Account.remove_from_google_workspace_group')
    @patch('orienteering_accounts.account.models.Account.remove_entry_rights_in_oris')
    def test_entry_rights_removed_when_balance_below_threshold(
        self, mock_remove_oris, mock_remove_google, mock_send_email
    ):
        """Test that entry rights are removed when balance falls below -2000 CZK"""
        # Create account with zero balance
        account = baker.make(
            'account.Account',
            init_balance=Decimal('0'),
            email='test@example.com',
            oris_club_member_id=12345,
            is_late_with_club_membership_payment=False
        )
        
        # Create a transaction that makes balance fall below -2000
        baker.make(
            'account.Transaction',
            account=account,
            amount=Decimal('-2500'),
            purpose=Transaction.TransactionPurpose.ENTRY
        )
        
        # Verify all actions were taken
        mock_remove_oris.assert_called_once()
        mock_remove_google.assert_called_once()
        mock_send_email.assert_called_once()
        
        # Verify the flag was set
        account.refresh_from_db()
        self.assertTrue(account.is_late_with_club_membership_payment)

    @patch('orienteering_accounts.account.models.Account.send_entry_rights_removed_info_email')
    @patch('orienteering_accounts.account.models.Account.remove_from_google_workspace_group')
    @patch('orienteering_accounts.account.models.Account.remove_entry_rights_in_oris')
    def test_entry_rights_not_removed_when_balance_above_threshold(
        self, mock_remove_oris, mock_remove_google, mock_send_email
    ):
        """Test that entry rights are NOT removed when balance is above -2000 CZK"""
        # Create account with zero balance
        account = baker.make(
            'account.Account',
            init_balance=Decimal('0'),
            email='test@example.com',
            oris_club_member_id=12345,
            is_late_with_club_membership_payment=False
        )
        
        # Create a transaction that makes balance negative but not below threshold
        baker.make(
            'account.Transaction',
            account=account,
            amount=Decimal('-1500'),
            purpose=Transaction.TransactionPurpose.ENTRY
        )
        
        # Verify no actions were taken
        mock_remove_oris.assert_not_called()
        mock_remove_google.assert_not_called()
        mock_send_email.assert_not_called()
        
        # Verify the flag was not set
        account.refresh_from_db()
        self.assertFalse(account.is_late_with_club_membership_payment)

    @patch('orienteering_accounts.account.models.Account.send_entry_rights_removed_info_email')
    @patch('orienteering_accounts.account.models.Account.remove_from_google_workspace_group')
    @patch('orienteering_accounts.account.models.Account.remove_entry_rights_in_oris')
    def test_entry_rights_not_removed_twice(
        self, mock_remove_oris, mock_remove_google, mock_send_email
    ):
        """Test that entry rights are NOT removed again if already removed"""
        # Create account with already removed rights
        account = baker.make(
            'account.Account',
            init_balance=Decimal('-3000'),
            email='test@example.com',
            oris_club_member_id=12345,
            is_late_with_club_membership_payment=True  # Already removed
        )
        
        # Create another negative transaction
        baker.make(
            'account.Transaction',
            account=account,
            amount=Decimal('-500'),
            purpose=Transaction.TransactionPurpose.ENTRY
        )
        
        # Verify no actions were taken (already removed)
        mock_remove_oris.assert_not_called()
        mock_remove_google.assert_not_called()
        mock_send_email.assert_not_called()

    @patch('orienteering_accounts.account.models.Account.send_entry_rights_removed_info_email')
    @patch('orienteering_accounts.account.models.Account.remove_from_google_workspace_group')
    @patch('orienteering_accounts.account.models.Account.remove_entry_rights_in_oris')
    def test_entry_rights_removed_exactly_at_threshold(
        self, mock_remove_oris, mock_remove_google, mock_send_email
    ):
        """Test that entry rights are removed when balance is exactly -2000 CZK"""
        # Create account with zero balance
        account = baker.make(
            'account.Account',
            init_balance=Decimal('0'),
            email='test@example.com',
            oris_club_member_id=12345,
            is_late_with_club_membership_payment=False
        )
        
        # Create a transaction that makes balance exactly -2000
        baker.make(
            'account.Transaction',
            account=account,
            amount=Decimal('-2000'),
            purpose=Transaction.TransactionPurpose.ENTRY
        )
        
        # Verify all actions were taken
        mock_remove_oris.assert_called_once()
        mock_remove_google.assert_called_once()
        mock_send_email.assert_called_once()
        
        # Verify the flag was set
        account.refresh_from_db()
        self.assertTrue(account.is_late_with_club_membership_payment)

    @patch('orienteering_accounts.account.models.Account.send_entry_rights_removed_info_email')
    @patch('orienteering_accounts.account.models.Account.remove_from_google_workspace_group')
    @patch('orienteering_accounts.account.models.Account.remove_entry_rights_in_oris')
    def test_entry_rights_removed_on_amount_update(
        self, mock_remove_oris, mock_remove_google, mock_send_email
    ):
        """Test that entry rights are removed when transaction amount is updated crossing threshold"""
        # Create account with balance slightly above threshold
        account = baker.make(
            'account.Account',
            init_balance=Decimal('0'),
            email='test@example.com',
            oris_club_member_id=12345,
            is_late_with_club_membership_payment=False
        )
        
        # Create a transaction that makes balance negative but above threshold
        transaction = baker.make(
            'account.Transaction',
            account=account,
            amount=Decimal('-1500'),
            purpose=Transaction.TransactionPurpose.ENTRY
        )
        
        # Reset mocks
        mock_remove_oris.reset_mock()
        mock_remove_google.reset_mock()
        mock_send_email.reset_mock()
        
        # Update transaction amount to cross the threshold
        transaction.amount = Decimal('-2500')
        transaction.save()
        
        # Verify all actions were taken
        mock_remove_oris.assert_called_once()
        mock_remove_google.assert_called_once()
        mock_send_email.assert_called_once()
        
        # Verify the flag was set
        account.refresh_from_db()
        self.assertTrue(account.is_late_with_club_membership_payment)

    @patch('orienteering_accounts.account.models.Account.send_entry_rights_removed_info_email')
    @patch('orienteering_accounts.account.models.Account.remove_from_google_workspace_group')
    @patch('orienteering_accounts.account.models.Account.remove_entry_rights_in_oris')
    def test_entry_rights_removed_on_transaction_deletion(
        self, mock_remove_oris, mock_remove_google, mock_send_email
    ):
        """Test that entry rights are removed when transaction deletion causes balance to cross threshold"""
        # Create account with negative balance kept above threshold by positive transaction
        account = baker.make(
            'account.Account',
            init_balance=Decimal('-2500'),
            email='test@example.com',
            oris_club_member_id=12345,
            is_late_with_club_membership_payment=False
        )
        
        # Create a positive transaction (balance becomes -1500, above threshold)
        transaction = baker.make(
            'account.Transaction',
            account=account,
            amount=Decimal('1000'),
            purpose=Transaction.TransactionPurpose.DEBTS
        )
        
        # Reset mocks
        mock_remove_oris.reset_mock()
        mock_remove_google.reset_mock()
        mock_send_email.reset_mock()
        
        # Delete the positive transaction (balance becomes -2500, below threshold)
        transaction.delete()
        
        # Verify all actions were taken
        mock_remove_oris.assert_called_once()
        mock_remove_google.assert_called_once()
        mock_send_email.assert_called_once()
        
        # Verify the flag was set
        account.refresh_from_db()
        self.assertTrue(account.is_late_with_club_membership_payment)

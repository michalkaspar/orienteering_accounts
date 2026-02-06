from datetime import datetime
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.utils import timezone
from freezegun import freeze_time
from model_bakery import baker

from orienteering_accounts.account.models import Account, BankTransaction, Transaction, PaymentPeriod
from orienteering_accounts.rb.models import (
    Transaction as BankTransactionSchema,
    TransactionAmount,
    BankTransactionCode,
    TransactionEntryDetails,
    TransactionDetails,
    RelatedParties,
    CounterParties,
    OrganisationIdentification,
    Account as BankAccount,
    RemittanceInformation,
    CreditorReferenceInformation
)


class ProcessBankTransactionTestCase(TestCase):
    """Test suite for Account.process_bank_transaction method"""

    def setUp(self):
        """Set up common test fixtures"""
        self.payment_period = baker.make('account.PaymentPeriod')
        
    def _create_bank_transaction_schema(
        self,
        entry_reference='TX123456',
        amount_value=100.0,
        variable_symbol=None,
        sender_name=None,
        receiver_note=None,
        constant_symbol=None,
        specific_symbol=None
    ):
        """Helper method to create a BankTransactionSchema object"""
        
        # Build remittance information
        creditor_ref = None
        if variable_symbol or constant_symbol or specific_symbol:
            creditor_ref = CreditorReferenceInformation(
                variable=variable_symbol,
                constant=constant_symbol,
                specific=specific_symbol
            )
        
        remittance_info = RemittanceInformation(
            unstructured=receiver_note,
            creditorReferenceInformation=creditor_ref,
            originatorMessage=receiver_note if not receiver_note else None
        )
        
        # Build counter party
        counter_party = None
        if sender_name:
            counter_party = CounterParties(
                name=sender_name,
                account=BankAccount(accountNumber='123456789'),
                organisationIdentification=OrganisationIdentification(bankCode='0100')
            )
        
        # Use timezone-aware datetime
        current_date = timezone.now().isoformat()
        
        # Build the full schema
        return BankTransactionSchema(
            entryReference=entry_reference,
            amount=TransactionAmount(value=amount_value, currency='CZK'),
            creditDebitIndication='CRDT',
            bookingDate=current_date,
            valueDate=current_date,
            bankTransactionCode=BankTransactionCode(code='PMNT'),
            entryDetails=TransactionEntryDetails(
                transactionDetails=TransactionDetails(
                    references={},
                    relatedParties=RelatedParties(counterParty=counter_party),
                    remittanceInformation=remittance_info
                )
            )
        )

    def test_all_transactions_saved_regardless_of_account_match(self):
        """Test that ALL bank transactions are saved, even without account match"""
        bank_transaction = self._create_bank_transaction_schema(
            entry_reference='TX_NO_MATCH',
            amount_value=500.0,
            variable_symbol='9999999999'  # No matching account
        )
        
        Account.process_bank_transaction(bank_transaction, self.payment_period)
        
        # Verify transaction was saved
        self.assertEqual(BankTransaction.objects.count(), 1)
        saved_transaction = BankTransaction.objects.first()
        
        self.assertEqual(saved_transaction.remote_id, 'TX_NO_MATCH')
        self.assertEqual(saved_transaction.amount, Decimal('500.0'))
        self.assertIsNone(saved_transaction.account)
        self.assertEqual(saved_transaction.purpose, BankTransaction.BankTransactionPurpose.UNKNOWN)
        self.assertFalse(saved_transaction.charged)

    def test_transaction_without_variable_symbol_saved(self):
        """Test that transactions without variable symbol are saved"""
        bank_transaction = self._create_bank_transaction_schema(
            entry_reference='TX_NO_VS',
            amount_value=1000.0,
            variable_symbol=None
        )
        
        Account.process_bank_transaction(bank_transaction, self.payment_period)
        
        self.assertEqual(BankTransaction.objects.count(), 1)
        saved_transaction = BankTransaction.objects.first()
        
        self.assertIsNone(saved_transaction.account)
        self.assertEqual(saved_transaction.purpose, BankTransaction.BankTransactionPurpose.UNKNOWN)
        self.assertFalse(saved_transaction.charged)

    def test_transaction_with_zero_amount_saved(self):
        """Test that transactions with amount <= 0 are saved but not charged"""
        bank_transaction = self._create_bank_transaction_schema(
            entry_reference='TX_ZERO',
            amount_value=0.0,
            variable_symbol='20261234'
        )
        
        Account.process_bank_transaction(bank_transaction, self.payment_period)
        
        self.assertEqual(BankTransaction.objects.count(), 1)
        saved_transaction = BankTransaction.objects.first()
        
        self.assertIsNone(saved_transaction.account)
        self.assertEqual(saved_transaction.amount, Decimal('0.0'))
        self.assertFalse(saved_transaction.charged)

    def test_transaction_with_negative_amount_saved(self):
        """Test that transactions with negative amount are saved"""
        bank_transaction = self._create_bank_transaction_schema(
            entry_reference='TX_NEGATIVE',
            amount_value=-50.0,
            variable_symbol='20261234'
        )
        
        Account.process_bank_transaction(bank_transaction, self.payment_period)
        
        self.assertEqual(BankTransaction.objects.count(), 1)
        saved_transaction = BankTransaction.objects.first()
        
        self.assertEqual(saved_transaction.amount, Decimal('-50.0'))
        self.assertFalse(saved_transaction.charged)

    @freeze_time("2026-02-06")
    def test_club_membership_payment_current_year(self):
        """Test club membership payment for current year matches and charges correctly"""
        account = baker.make(
            'account.Account',
            registration_number='TZL1234',
            is_active=False,
            removed_from_google_workspace=False
        )
        
        bank_transaction = self._create_bank_transaction_schema(
            entry_reference='TX_MEMBER_2026',
            amount_value=500.0,
            variable_symbol='20261234',
            sender_name='John Doe',
            receiver_note='Club membership 2026'
        )
        
        with patch.object(Account, 'add_to_google_workspace_group'):
            Account.process_bank_transaction(bank_transaction, self.payment_period)
        
        # Verify BankTransaction was created and linked
        self.assertEqual(BankTransaction.objects.count(), 1)
        saved_bank_transaction = BankTransaction.objects.first()
        
        self.assertEqual(saved_bank_transaction.account, account)
        self.assertEqual(saved_bank_transaction.purpose, BankTransaction.BankTransactionPurpose.CLUB_MEMBERSHIP)
        self.assertTrue(saved_bank_transaction.charged)
        self.assertEqual(saved_bank_transaction.sender_name, 'John Doe')
        self.assertEqual(saved_bank_transaction.receiver_note, 'Club membership 2026')
        
        # Verify Account Transaction was created
        self.assertEqual(Transaction.objects.count(), 1)
        transaction = Transaction.objects.first()
        
        self.assertEqual(transaction.account, account)
        self.assertEqual(transaction.amount, Decimal('500.0'))
        self.assertEqual(transaction.purpose, Transaction.TransactionPurpose.CLUB_MEMBERSHIP)
        self.assertEqual(transaction.period, self.payment_period)
        self.assertEqual(transaction.origin_bank_transaction, saved_bank_transaction)
        self.assertEqual(transaction.note, 'Importováno z IB.')
        self.assertEqual(transaction.author_name, 'Systém')
        
        # Verify account was activated
        account.refresh_from_db()
        self.assertTrue(account.is_active)

    @freeze_time("2026-02-06")
    def test_club_membership_payment_previous_year(self):
        """Test club membership payment for previous year matches correctly"""
        account = baker.make('account.Account', registration_number='TZL5678')
        
        bank_transaction = self._create_bank_transaction_schema(
            entry_reference='TX_MEMBER_2025',
            amount_value=450.0,
            variable_symbol='20255678'
        )
        
        Account.process_bank_transaction(bank_transaction, self.payment_period)
        
        saved_bank_transaction = BankTransaction.objects.first()
        self.assertEqual(saved_bank_transaction.account, account)
        self.assertEqual(saved_bank_transaction.purpose, BankTransaction.BankTransactionPurpose.CLUB_MEMBERSHIP)
        self.assertTrue(saved_bank_transaction.charged)

    def test_debts_payment_with_1000_prefix(self):
        """Test debt payment with 1000 prefix matches correctly"""
        account = baker.make('account.Account', registration_number='TZL9999')
        
        bank_transaction = self._create_bank_transaction_schema(
            entry_reference='TX_DEBT_1000',
            amount_value=300.0,
            variable_symbol='10009999'
        )
        
        Account.process_bank_transaction(bank_transaction, self.payment_period)
        
        # Verify BankTransaction
        saved_bank_transaction = BankTransaction.objects.first()
        self.assertEqual(saved_bank_transaction.account, account)
        self.assertEqual(saved_bank_transaction.purpose, BankTransaction.BankTransactionPurpose.DEBTS)
        self.assertTrue(saved_bank_transaction.charged)
        
        # Verify Transaction
        transaction = Transaction.objects.first()
        self.assertEqual(transaction.purpose, Transaction.TransactionPurpose.DEBTS)
        self.assertIsNone(transaction.period)

    def test_debts_payment_with_1001_prefix(self):
        """Test debt payment with 1001 prefix matches correctly"""
        account = baker.make('account.Account', registration_number='TZL8888')
        
        bank_transaction = self._create_bank_transaction_schema(
            entry_reference='TX_DEBT_1001',
            amount_value=250.0,
            variable_symbol='10018888'
        )
        
        Account.process_bank_transaction(bank_transaction, self.payment_period)
        
        saved_bank_transaction = BankTransaction.objects.first()
        self.assertEqual(saved_bank_transaction.account, account)
        self.assertEqual(saved_bank_transaction.purpose, BankTransaction.BankTransactionPurpose.DEBTS)

    def test_variable_symbol_with_leading_zeros(self):
        """Test that variable symbol with leading zeros is handled correctly"""
        account = baker.make('account.Account', registration_number='TZL1234')
        
        bank_transaction = self._create_bank_transaction_schema(
            entry_reference='TX_LEADING_ZEROS',
            amount_value=400.0,
            variable_symbol='0000020261234'  # Leading zeros
        )
        
        with freeze_time("2026-02-06"):
            Account.process_bank_transaction(bank_transaction, self.payment_period)
        
        saved_bank_transaction = BankTransaction.objects.first()
        self.assertEqual(saved_bank_transaction.account, account)
        self.assertTrue(saved_bank_transaction.charged)

    def test_transaction_not_duplicated(self):
        """Test that duplicate transactions (same entryReference) are not created"""
        account = baker.make('account.Account', registration_number='TZL1234')
        
        bank_transaction = self._create_bank_transaction_schema(
            entry_reference='TX_DUPLICATE',
            amount_value=500.0,
            variable_symbol='20261234'
        )
        
        with freeze_time("2026-02-06"):
            # Process same transaction twice
            Account.process_bank_transaction(bank_transaction, self.payment_period)
            Account.process_bank_transaction(bank_transaction, self.payment_period)
        
        # Should only have one BankTransaction
        self.assertEqual(BankTransaction.objects.count(), 1)
        # Should only have one Transaction
        self.assertEqual(Transaction.objects.count(), 1)

    @patch.object(Account, 'add_to_google_workspace_group')
    def test_google_workspace_added_when_removed(self, mock_add_to_google):
        """Test that account is added back to Google Workspace when it was removed"""
        account = baker.make(
            'account.Account',
            registration_number='TZL1234',
            is_active=False,
            removed_from_google_workspace=True
        )
        
        bank_transaction = self._create_bank_transaction_schema(
            entry_reference='TX_GOOGLE',
            amount_value=500.0,
            variable_symbol='20261234'
        )
        
        with freeze_time("2026-02-06"):
            Account.process_bank_transaction(bank_transaction, self.payment_period)
        
        # Verify Google Workspace group was called
        mock_add_to_google.assert_called_once()
        
        # Verify flag was updated
        account.refresh_from_db()
        self.assertFalse(account.removed_from_google_workspace)

    @patch.object(Account, 'add_to_google_workspace_group')
    def test_google_workspace_not_called_when_not_removed(self, mock_add_to_google):
        """Test that Google Workspace is not called if account was not removed"""
        account = baker.make(
            'account.Account',
            registration_number='TZL1234',
            removed_from_google_workspace=False
        )
        
        bank_transaction = self._create_bank_transaction_schema(
            entry_reference='TX_GOOGLE_NOT_REMOVED',
            amount_value=500.0,
            variable_symbol='20261234'
        )
        
        with freeze_time("2026-02-06"):
            Account.process_bank_transaction(bank_transaction, self.payment_period)
        
        # Verify Google Workspace was not called
        mock_add_to_google.assert_not_called()

    def test_sender_name_extraction(self):
        """Test that sender name is extracted correctly from counterParty"""
        bank_transaction = self._create_bank_transaction_schema(
            entry_reference='TX_SENDER',
            amount_value=100.0,
            sender_name='Jane Smith'
        )
        
        Account.process_bank_transaction(bank_transaction, self.payment_period)
        
        saved_transaction = BankTransaction.objects.first()
        self.assertEqual(saved_transaction.sender_name, 'Jane Smith')

    def test_receiver_note_extraction_from_unstructured(self):
        """Test that receiver note is extracted from unstructured field"""
        bank_transaction = self._create_bank_transaction_schema(
            entry_reference='TX_NOTE_UNSTR',
            amount_value=100.0,
            receiver_note='Payment for services'
        )
        
        Account.process_bank_transaction(bank_transaction, self.payment_period)
        
        saved_transaction = BankTransaction.objects.first()
        self.assertEqual(saved_transaction.receiver_note, 'Payment for services')

    def test_receiver_note_extraction_from_originator_message(self):
        """Test that receiver note falls back to originatorMessage"""
        # Create schema manually to control originatorMessage
        current_date = timezone.now().isoformat()
        bank_transaction = BankTransactionSchema(
            entryReference='TX_NOTE_ORIG',
            amount=TransactionAmount(value=100.0, currency='CZK'),
            creditDebitIndication='CRDT',
            bookingDate=current_date,
            valueDate=current_date,
            bankTransactionCode=BankTransactionCode(code='PMNT'),
            entryDetails=TransactionEntryDetails(
                transactionDetails=TransactionDetails(
                    references={},
                    relatedParties=RelatedParties(),
                    remittanceInformation=RemittanceInformation(
                        originatorMessage='Message from originator',
                        creditorReferenceInformation=None
                    )
                )
            )
        )
        
        Account.process_bank_transaction(bank_transaction, self.payment_period)
        
        saved_transaction = BankTransaction.objects.first()
        self.assertEqual(saved_transaction.receiver_note, 'Message from originator')

    def test_transaction_data_stored_as_json(self):
        """Test that full transaction data is stored as JSON"""
        bank_transaction = self._create_bank_transaction_schema(
            entry_reference='TX_JSON',
            amount_value=500.0,
            variable_symbol='20261234',
            sender_name='Test User'
        )
        
        with freeze_time("2026-02-06"):
            account = baker.make('account.Account', registration_number='TZL1234')
            Account.process_bank_transaction(bank_transaction, self.payment_period)
        
        saved_transaction = BankTransaction.objects.first()
        
        # Verify transaction_data contains expected fields
        self.assertIn('entryReference', saved_transaction.transaction_data)
        self.assertIn('amount', saved_transaction.transaction_data)
        self.assertIn('entryDetails', saved_transaction.transaction_data)
        self.assertEqual(saved_transaction.transaction_data['entryReference'], 'TX_JSON')

    def test_invalid_variable_symbol_format(self):
        """Test that transactions with invalid variable symbol format are saved as unknown"""
        bank_transaction = self._create_bank_transaction_schema(
            entry_reference='TX_INVALID_VS',
            amount_value=200.0,
            variable_symbol='ABCD1234'  # Invalid format
        )
        
        Account.process_bank_transaction(bank_transaction, self.payment_period)
        
        saved_transaction = BankTransaction.objects.first()
        self.assertIsNone(saved_transaction.account)
        self.assertEqual(saved_transaction.purpose, BankTransaction.BankTransactionPurpose.UNKNOWN)
        self.assertFalse(saved_transaction.charged)

    def test_variable_symbol_without_matching_prefix(self):
        """Test that variable symbol without valid prefix is saved as unknown"""
        baker.make('account.Account', registration_number='TZL1234')
        
        bank_transaction = self._create_bank_transaction_schema(
            entry_reference='TX_WRONG_PREFIX',
            amount_value=300.0,
            variable_symbol='30001234'  # Wrong prefix (3000)
        )
        
        Account.process_bank_transaction(bank_transaction, self.payment_period)
        
        saved_transaction = BankTransaction.objects.first()
        self.assertIsNone(saved_transaction.account)
        self.assertEqual(saved_transaction.purpose, BankTransaction.BankTransactionPurpose.UNKNOWN)

    def test_account_not_found_by_registration_number(self):
        """Test transaction when account with registration number doesn't exist"""
        # Don't create any account
        
        bank_transaction = self._create_bank_transaction_schema(
            entry_reference='TX_NO_ACCOUNT',
            amount_value=400.0,
            variable_symbol='20269999'
        )
        
        with freeze_time("2026-02-06"):
            Account.process_bank_transaction(bank_transaction, self.payment_period)
        
        # BankTransaction should be saved without account
        saved_transaction = BankTransaction.objects.first()
        self.assertIsNone(saved_transaction.account)
        self.assertEqual(saved_transaction.purpose, BankTransaction.BankTransactionPurpose.UNKNOWN)
        self.assertFalse(saved_transaction.charged)
        
        # No Account Transaction should be created
        self.assertEqual(Transaction.objects.count(), 0)

    def test_inactive_account_activated_on_membership_payment(self):
        """Test that inactive account becomes active on membership payment"""
        account = baker.make(
            'account.Account',
            registration_number='TZL5555',
            is_active=False
        )
        
        bank_transaction = self._create_bank_transaction_schema(
            entry_reference='TX_ACTIVATE',
            amount_value=500.0,
            variable_symbol='20265555'
        )
        
        with freeze_time("2026-02-06"):
            Account.process_bank_transaction(bank_transaction, self.payment_period)
        
        account.refresh_from_db()
        self.assertTrue(account.is_active)

    def test_active_account_stays_active_on_debt_payment(self):
        """Test that active account stays active on debt payment (no change)"""
        account = baker.make(
            'account.Account',
            registration_number='TZL7777',
            is_active=True
        )
        
        bank_transaction = self._create_bank_transaction_schema(
            entry_reference='TX_DEBT_ACTIVE',
            amount_value=200.0,
            variable_symbol='10007777'
        )
        
        Account.process_bank_transaction(bank_transaction, self.payment_period)
        
        account.refresh_from_db()
        self.assertTrue(account.is_active)

    def test_missing_sender_info_handled_gracefully(self):
        """Test that missing sender information doesn't cause errors"""
        current_date = timezone.now().isoformat()
        bank_transaction = BankTransactionSchema(
            entryReference='TX_NO_SENDER',
            amount=TransactionAmount(value=100.0, currency='CZK'),
            creditDebitIndication='CRDT',
            bookingDate=current_date,
            valueDate=current_date,
            bankTransactionCode=BankTransactionCode(code='PMNT'),
            entryDetails=TransactionEntryDetails(
                transactionDetails=TransactionDetails(
                    references={},
                    relatedParties=RelatedParties(counterParty=None),
                    remittanceInformation=None
                )
            )
        )
        
        Account.process_bank_transaction(bank_transaction, self.payment_period)
        
        saved_transaction = BankTransaction.objects.first()
        self.assertEqual(saved_transaction.sender_name, '')
        self.assertEqual(saved_transaction.receiver_note, '')

    def test_missing_remittance_info_handled_gracefully(self):
        """Test that missing remittance information doesn't cause errors"""
        current_date = timezone.now().isoformat()
        bank_transaction = BankTransactionSchema(
            entryReference='TX_NO_REMITTANCE',
            amount=TransactionAmount(value=100.0, currency='CZK'),
            creditDebitIndication='CRDT',
            bookingDate=current_date,
            valueDate=current_date,
            bankTransactionCode=BankTransactionCode(code='PMNT'),
            entryDetails=TransactionEntryDetails(
                transactionDetails=TransactionDetails(
                    references={},
                    relatedParties=RelatedParties(),
                    remittanceInformation=None
                )
            )
        )
        
        Account.process_bank_transaction(bank_transaction, self.payment_period)
        
        saved_transaction = BankTransaction.objects.first()
        self.assertEqual(saved_transaction.receiver_note, '')

    @freeze_time("2026-02-06")
    def test_multiple_transactions_for_same_account(self):
        """Test processing multiple transactions for the same account"""
        account = baker.make('account.Account', registration_number='TZL1111')
        
        # Process multiple transactions
        for i in range(3):
            bank_transaction = self._create_bank_transaction_schema(
                entry_reference=f'TX_MULTI_{i}',
                amount_value=100.0 + i * 50,
                variable_symbol='20261111'
            )
            Account.process_bank_transaction(bank_transaction, self.payment_period)
        
        # Should have 3 BankTransactions
        self.assertEqual(BankTransaction.objects.count(), 3)
        self.assertEqual(BankTransaction.objects.filter(account=account).count(), 3)
        
        # Should have 3 Account Transactions
        self.assertEqual(Transaction.objects.count(), 3)
        self.assertEqual(Transaction.objects.filter(account=account).count(), 3)

    def test_transaction_with_all_optional_fields(self):
        """Test transaction with all optional fields populated"""
        account = baker.make('account.Account', registration_number='TZL1234')
        
        bank_transaction = self._create_bank_transaction_schema(
            entry_reference='TX_FULL',
            amount_value=500.0,
            variable_symbol='20261234',
            sender_name='Complete Sender Name',
            receiver_note='Complete receiver note with details',
            constant_symbol='0308',
            specific_symbol='1234567890'
        )
        
        with freeze_time("2026-02-06"):
            Account.process_bank_transaction(bank_transaction, self.payment_period)
        
        saved_transaction = BankTransaction.objects.first()
        self.assertEqual(saved_transaction.sender_name, 'Complete Sender Name')
        self.assertEqual(saved_transaction.receiver_note, 'Complete receiver note with details')
        
        # Check that all data is in transaction_data
        self.assertIn('entryDetails', saved_transaction.transaction_data)
        remittance = saved_transaction.transaction_data['entryDetails']['transactionDetails']['remittanceInformation']
        self.assertEqual(remittance['creditorReferenceInformation']['constant'], '0308')
        self.assertEqual(remittance['creditorReferenceInformation']['specific'], '1234567890')

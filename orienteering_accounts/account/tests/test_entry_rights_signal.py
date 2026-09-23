from decimal import Decimal
from unittest import mock

from django.conf import settings
from django.test import TestCase
from model_bakery import baker

from orienteering_accounts.account.models import Transaction


class EntryRightsSignalTestCase(TestCase):

    def setUp(self):
        for target in [
            'orienteering_accounts.account.models.Account.send_debts_payment_info_email',
            'orienteering_accounts.account.models.Account.send_entry_rights_removed_info_email',
            'orienteering_accounts.account.models.Account.send_entry_rights_restored_info_email',
        ]:
            patcher = mock.patch(target)
            patcher.start()
            self.addCleanup(patcher.stop)

        add_patcher = mock.patch('orienteering_accounts.account.models.Account.add_entry_rights_in_oris')
        self.add_rights_mock = add_patcher.start()
        self.addCleanup(add_patcher.stop)

        remove_patcher = mock.patch('orienteering_accounts.account.models.Account.remove_entry_rights_in_oris')
        self.remove_rights_mock = remove_patcher.start()
        self.addCleanup(remove_patcher.stop)

        self.threshold = Decimal(str(settings.MAXIMUM_NEGATIVE_BALANCE))
        self.account = baker.make('account.Account', init_balance=Decimal('0'), oris_club_member_id=11)

    def _add_transaction(self, amount):
        with self.captureOnCommitCallbacks(execute=True):
            return baker.make(
                Transaction,
                account=self.account,
                amount=amount,
                purpose=Transaction.TransactionPurpose.ENTRY,
            )

    def test_transaction_above_threshold_does_not_touch_oris(self):
        self._add_transaction(Decimal('-100'))

        self.add_rights_mock.assert_not_called()
        self.remove_rights_mock.assert_not_called()

    def test_crossing_threshold_downwards_removes_rights_once(self):
        self._add_transaction(self.threshold - Decimal('100'))

        self.remove_rights_mock.assert_called_once()
        self.add_rights_mock.assert_not_called()

    def test_crossing_threshold_upwards_restores_rights_once(self):
        self._add_transaction(self.threshold - Decimal('100'))
        self.remove_rights_mock.reset_mock()

        self._add_transaction(Decimal('5000'))

        self.add_rights_mock.assert_called_once()

    def test_deleting_a_transaction_without_crossing_does_not_touch_oris(self):
        created = self._add_transaction(Decimal('-100'))
        self.add_rights_mock.reset_mock()

        with self.captureOnCommitCallbacks(execute=True):
            created.delete()

        self.add_rights_mock.assert_not_called()
        self.remove_rights_mock.assert_not_called()

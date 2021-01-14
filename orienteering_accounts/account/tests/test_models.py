from datetime import timedelta
from decimal import Decimal

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

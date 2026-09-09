from datetime import datetime
from decimal import Decimal
from unittest.mock import PropertyMock, patch

from django.test import TestCase
from model_bakery import baker

from orienteering_accounts.account import signals
from orienteering_accounts.account.models import Account, Transaction
from orienteering_accounts.entry.models import Entry
from orienteering_accounts.oris.models import Entry as OrisEntry


def _oris_entry(user_id=1234, oris_id=42, **overrides):
    payload = {
        'ID': oris_id,
        'UserID': user_id,
        'ClassID': 7,
        'ClassDesc': 'M21',
        'CreatedDateTime': datetime(2026, 1, 1, 10, 0, 0).isoformat(),
        'UpdatedDateTime': None,
        'Fee': 200,
        'RentSI': False,
        'ClubNote': '',
    }
    payload.update(overrides)
    return OrisEntry(**payload)


def _service(id_, name='Tricko', total_fee='100'):
    return {'Service': {'ID': id_, 'NameCZ': name}, 'TotalFee': total_fee}


class EntryUpsertFromOrisTestCase(TestCase):

    def setUp(self):
        signals._pending_balance_checks.clear()
        signal_targets = [
            'orienteering_accounts.account.models.Account.send_debts_payment_info_email',
            'orienteering_accounts.account.models.Account.send_entry_rights_removed_info_email',
            'orienteering_accounts.account.models.Account.remove_from_google_workspace_group',
            'orienteering_accounts.account.models.Account.remove_entry_rights_in_oris',
            'orienteering_accounts.account.models.Account.add_entry_rights_in_oris',
        ]
        for target in signal_targets:
            patcher = patch(target)
            patcher.start()
            self.addCleanup(patcher.stop)

        fee_patcher = patch.object(
            Entry,
            'fee_after_club_discount_future',
            new_callable=PropertyMock,
            return_value=Decimal('0'),
        )
        fee_patcher.start()
        self.addCleanup(fee_patcher.stop)

        self.account = baker.make('account.Account', oris_id=1234)
        self.event = baker.make('event.Event', exchange_rate=Decimal('1'))

    def _service_txns(self, entry):
        return entry.transactions.filter(
            purpose=Transaction.TransactionPurpose.ENTRY_OTHER,
            is_future=True,
            author_name='System',
        )

    def _entry_txns(self, entry):
        return entry.transactions.filter(purpose=Transaction.TransactionPurpose.ENTRY)

    def test_initial_create_with_services_creates_service_transactions(self):
        services = [_service(1, 'Tricko', '100'), _service(2, 'Bunda', '250')]

        entry = Entry.upsert_from_oris(_oris_entry(user_id=1234), self.event, services)

        self.assertIsNotNone(entry)
        self.assertEqual(self._entry_txns(entry).count(), 1)
        self.assertEqual(self._service_txns(entry).count(), 2)
        self.assertEqual(
            self._service_txns(entry).get(note='Tricko').amount, Decimal('-100')
        )
        self.assertEqual(
            self._service_txns(entry).get(note='Bunda').amount, Decimal('-250')
        )

    def test_initial_create_with_no_services_creates_only_entry_transaction(self):
        entry = Entry.upsert_from_oris(_oris_entry(user_id=1234), self.event, [])

        self.assertIsNotNone(entry)
        self.assertEqual(self._entry_txns(entry).count(), 1)
        self.assertEqual(self._service_txns(entry).count(), 0)

    def test_update_adds_new_service(self):
        entry = Entry.upsert_from_oris(
            _oris_entry(user_id=1234), self.event, [_service(1, 'Tricko', '100')]
        )
        a_id = self._service_txns(entry).get(note='Tricko').pk

        Entry.upsert_from_oris(
            _oris_entry(user_id=1234),
            self.event,
            [_service(1, 'Tricko', '100'), _service(2, 'Bunda', '250')],
        )

        self.assertEqual(self._entry_txns(entry).count(), 1)
        self.assertEqual(self._service_txns(entry).count(), 2)
        self.assertTrue(self._service_txns(entry).filter(pk=a_id).exists())
        self.assertEqual(
            self._service_txns(entry).get(note='Bunda').amount, Decimal('-250')
        )

    def test_update_removes_service_deletes_matching_transaction(self):
        entry = Entry.upsert_from_oris(
            _oris_entry(user_id=1234),
            self.event,
            [_service(1, 'Tricko', '100'), _service(2, 'Bunda', '250')],
        )
        a_id = self._service_txns(entry).get(note='Tricko').pk

        Entry.upsert_from_oris(
            _oris_entry(user_id=1234), self.event, [_service(1, 'Tricko', '100')]
        )

        self.assertEqual(self._service_txns(entry).count(), 1)
        self.assertTrue(self._service_txns(entry).filter(pk=a_id).exists())
        self.assertFalse(self._service_txns(entry).filter(note='Bunda').exists())

    def test_update_with_unchanged_services_is_noop(self):
        services = [_service(1, 'Tricko', '100'), _service(2, 'Bunda', '250')]
        entry = Entry.upsert_from_oris(_oris_entry(user_id=1234), self.event, services)
        original_ids = set(self._service_txns(entry).values_list('pk', flat=True))

        Entry.upsert_from_oris(_oris_entry(user_id=1234), self.event, services)

        self.assertEqual(
            set(self._service_txns(entry).values_list('pk', flat=True)), original_ids
        )
        self.assertEqual(self._entry_txns(entry).count(), 1)

    def test_update_full_replace_swaps_transactions(self):
        entry = Entry.upsert_from_oris(
            _oris_entry(user_id=1234),
            self.event,
            [_service(1, 'Tricko', '100'), _service(2, 'Bunda', '250')],
        )

        Entry.upsert_from_oris(
            _oris_entry(user_id=1234),
            self.event,
            [_service(3, 'Mapa', '50'), _service(4, 'Cip', '500')],
        )

        notes = set(self._service_txns(entry).values_list('note', flat=True))
        self.assertEqual(notes, {'Mapa', 'Cip'})
        self.assertEqual(self._service_txns(entry).count(), 2)

    def test_update_when_existing_additional_services_is_default_dict(self):
        entry = Entry.objects.create(
            account=self.account,
            event=self.event,
            oris_id=42,
            oris_category_id=7,
            category_name='M21',
            fee=200,
            additional_services={},
        )

        Entry.upsert_from_oris(
            _oris_entry(user_id=1234), self.event, [_service(1, 'Tricko', '100')]
        )

        self.assertEqual(self._service_txns(entry).count(), 1)
        self.assertEqual(
            self._service_txns(entry).get(note='Tricko').amount, Decimal('-100')
        )

    def test_invalid_entry_returns_none_and_creates_nothing(self):
        result = Entry.upsert_from_oris(
            _oris_entry(user_id=None), self.event, [_service(1)]
        )

        self.assertIsNone(result)
        self.assertEqual(Entry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_account_not_found_returns_none(self):
        result = Entry.upsert_from_oris(
            _oris_entry(user_id=999999), self.event, [_service(1)]
        )

        self.assertIsNone(result)
        self.assertEqual(Entry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_currency_conversion_applied_to_service_amount(self):
        eur_event = baker.make('event.Event', exchange_rate=Decimal('25'))

        entry = Entry.upsert_from_oris(
            _oris_entry(user_id=1234), eur_event, [_service(1, 'Tricko', '10')]
        )

        self.assertEqual(
            self._service_txns(entry).get(note='Tricko').amount, Decimal('-250')
        )

    def test_stale_deletion_removes_all_duplicates_when_notes_collide(self):
        entry = Entry.upsert_from_oris(
            _oris_entry(user_id=1234), self.event, [_service(1, 'Tricko', '100')]
        )
        older = self._service_txns(entry).get(note='Tricko')
        newer = entry.transactions.create(
            account=self.account,
            amount=Decimal('-100'),
            purpose=Transaction.TransactionPurpose.ENTRY_OTHER,
            author_name='System',
            note='Tricko',
            is_future=True,
        )

        Entry.upsert_from_oris(_oris_entry(user_id=1234), self.event, [])

        self.assertFalse(self._service_txns(entry).filter(pk=older.pk).exists())
        self.assertFalse(self._service_txns(entry).filter(pk=newer.pk).exists())

    def test_initial_create_with_duplicate_service_id_sums_into_one_transaction(self):
        services = [
            _service(1, 'Ubytování v kempu', '1500'),
            _service(1, 'Ubytování v kempu', '300'),
        ]

        entry = Entry.upsert_from_oris(_oris_entry(user_id=1234), self.event, services)

        self.assertEqual(self._service_txns(entry).count(), 1)
        self.assertEqual(
            self._service_txns(entry).get(note='Ubytování v kempu').amount, Decimal('-1800')
        )

    def test_update_adds_second_line_for_existing_service_updates_amount(self):
        entry = Entry.upsert_from_oris(
            _oris_entry(user_id=1234),
            self.event,
            [_service(1, 'Ubytování v kempu', '1500')],
        )
        txn_id = self._service_txns(entry).get(note='Ubytování v kempu').pk

        Entry.upsert_from_oris(
            _oris_entry(user_id=1234),
            self.event,
            [
                _service(1, 'Ubytování v kempu', '1500'),
                _service(1, 'Ubytování v kempu', '300'),
            ],
        )

        self.assertEqual(self._service_txns(entry).count(), 1)
        updated = self._service_txns(entry).get(note='Ubytování v kempu')
        self.assertEqual(updated.pk, txn_id)
        self.assertEqual(updated.amount, Decimal('-1800'))

    def test_update_removing_second_line_reduces_amount_back(self):
        entry = Entry.upsert_from_oris(
            _oris_entry(user_id=1234),
            self.event,
            [
                _service(1, 'Ubytování v kempu', '1500'),
                _service(1, 'Ubytování v kempu', '300'),
            ],
        )

        Entry.upsert_from_oris(
            _oris_entry(user_id=1234),
            self.event,
            [_service(1, 'Ubytování v kempu', '1500')],
        )

        self.assertEqual(self._service_txns(entry).count(), 1)
        self.assertEqual(
            self._service_txns(entry).get(note='Ubytování v kempu').amount, Decimal('-1500')
        )


class EntryUpsertServicesOnlyFromOrisTestCase(EntryUpsertFromOrisTestCase):

    def test_creates_placeholder_entry_with_service_transactions(self):
        services = [_service(1, 'Tricko', '100'), _service(2, 'Bunda', '250')]

        entry = Entry.upsert_services_only_from_oris(1234, self.event, services)

        self.assertIsNotNone(entry)
        self.assertTrue(entry.services_only)
        self.assertEqual(entry.oris_id, None)
        self.assertEqual(entry.oris_category_id, 0)
        self.assertEqual(entry.category_name, '')
        self.assertEqual(entry.fee, 0)
        self.assertEqual(self._entry_txns(entry).count(), 1)
        self.assertEqual(self._service_txns(entry).count(), 2)
        self.assertEqual(entry.debt_init, Decimal('350'))

    def test_account_not_found_returns_none(self):
        result = Entry.upsert_services_only_from_oris(999999, self.event, [_service(1)])

        self.assertIsNone(result)
        self.assertEqual(Entry.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_service_only_entry_later_matched_by_real_entry_upgrades_in_place(self):
        placeholder = Entry.upsert_services_only_from_oris(
            1234, self.event, [_service(1, 'Tricko', '100')]
        )

        upgraded = Entry.upsert_from_oris(
            _oris_entry(user_id=1234), self.event, [_service(1, 'Tricko', '100')]
        )

        self.assertEqual(placeholder.pk, upgraded.pk)
        self.assertFalse(upgraded.services_only)
        self.assertEqual(upgraded.oris_category_id, 7)
        self.assertEqual(upgraded.category_name, 'M21')
        self.assertEqual(self._service_txns(upgraded).count(), 1)

    def test_real_entry_that_drops_race_entry_downgrades_in_place(self):
        real = Entry.upsert_from_oris(
            _oris_entry(user_id=1234), self.event, [_service(1, 'Tricko', '100')]
        )

        downgraded = Entry.upsert_services_only_from_oris(
            1234, self.event, [_service(1, 'Tricko', '100')]
        )

        self.assertEqual(real.pk, downgraded.pk)
        self.assertTrue(downgraded.services_only)
        self.assertEqual(downgraded.oris_category_id, 0)
        self.assertEqual(downgraded.category_name, '')
        self.assertEqual(downgraded.fee, 0)
        self.assertEqual(self._service_txns(downgraded).count(), 1)

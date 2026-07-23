from datetime import datetime
from decimal import Decimal
from unittest.mock import PropertyMock, patch

from django.test import TestCase
from model_bakery import baker

from orienteering_accounts.entry.models import Entry
from orienteering_accounts.oris.models import Entry as OrisEntry, LegEntry


def _oris_entry(user_id, oris_id=42, **overrides):
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


def _leg_entry(registration_number, **overrides):
    payload = {
        'ClassID': 7,
        'ClassDesc': 'M21',
        'CreatedDateTime': datetime(2026, 1, 1, 10, 0, 0).isoformat(),
        'UpdatedDateTime': None,
        'RegNo': registration_number,
    }
    payload.update(overrides)
    return LegEntry(**payload)


def _service(user_id, reg_no, id_=1, name='Tricko', total_fee='100'):
    return {'UserID': user_id, 'RegNo': reg_no, 'Service': {'ID': id_, 'NameCZ': name}, 'TotalFee': total_fee}


class UpdateEntriesTestCase(TestCase):

    def setUp(self):
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

        self.event = baker.make('event.Event', exchange_rate=Decimal('1'))

    def test_orphan_service_order_creates_services_only_entry(self):
        racer = baker.make('account.Account', oris_id=1111, registration_number='AAA0001')
        merch_only = baker.make('account.Account', oris_id=2222, registration_number='AAA0002')

        with patch(
            'orienteering_accounts.oris.client.ORISClient.get_event_entries',
            return_value=[_oris_entry(user_id=1111)],
        ), patch(
            'orienteering_accounts.oris.client.ORISClient.get_event_additional_services',
            return_value={
                1111: [_service(1111, 'AAA0001', id_=1, name='Tricko')],
                2222: [_service(2222, 'AAA0002', id_=2, name='Bunda')],
            },
        ):
            self.event.update_entries()

        self.assertEqual(self.event.entries.count(), 2)
        racer_entry = self.event.entries.get(account=racer)
        merch_entry = self.event.entries.get(account=merch_only)
        self.assertFalse(racer_entry.services_only)
        self.assertTrue(merch_entry.services_only)
        self.assertEqual(merch_entry.oris_category_id, 0)
        self.assertEqual(merch_entry.category_name, '')
        self.assertEqual(merch_entry.debt_init, Decimal('100'))

    def test_service_claimed_by_real_entry_does_not_also_create_placeholder(self):
        baker.make('account.Account', oris_id=1111, registration_number='AAA0001')

        with patch(
            'orienteering_accounts.oris.client.ORISClient.get_event_entries',
            return_value=[_oris_entry(user_id=1111)],
        ), patch(
            'orienteering_accounts.oris.client.ORISClient.get_event_additional_services',
            return_value={1111: [_service(1111, 'AAA0001', id_=1, name='Tricko')]},
        ):
            self.event.update_entries()

        self.assertEqual(self.event.entries.count(), 1)
        self.assertFalse(self.event.entries.first().services_only)

    def test_relay_leg_entry_claims_service_by_registration_number(self):
        racer = baker.make('account.Account', oris_id=3333, registration_number='ABC0001')

        with patch(
            'orienteering_accounts.oris.client.ORISClient.get_event_entries',
            return_value=[_leg_entry(registration_number='ABC0001')],
        ), patch(
            'orienteering_accounts.oris.client.ORISClient.get_event_additional_services',
            return_value={3333: [_service(3333, 'ABC0001', id_=1, name='Tricko')]},
        ):
            self.event.update_entries()

        self.assertEqual(self.event.entries.count(), 1)
        self.assertFalse(self.event.entries.get(account=racer).services_only)

    def test_relay_event_unclaimed_service_becomes_services_only_entry(self):
        racer = baker.make('account.Account', oris_id=4444, registration_number='XYZ0002')
        merch_only = baker.make('account.Account', oris_id=5555, registration_number='XYZ0003')

        with patch(
            'orienteering_accounts.oris.client.ORISClient.get_event_entries',
            return_value=[_leg_entry(registration_number='XYZ0002')],
        ), patch(
            'orienteering_accounts.oris.client.ORISClient.get_event_additional_services',
            return_value={
                4444: [_service(4444, 'XYZ0002', id_=1, name='Tricko')],
                5555: [_service(5555, 'XYZ0003', id_=2, name='Bunda')],
            },
        ):
            self.event.update_entries()

        self.assertEqual(self.event.entries.count(), 2)
        self.assertFalse(self.event.entries.get(account=racer).services_only)
        self.assertTrue(self.event.entries.get(account=merch_only).services_only)

    def test_orphan_with_unknown_account_is_skipped(self):
        with patch(
            'orienteering_accounts.oris.client.ORISClient.get_event_entries',
            return_value=[],
        ), patch(
            'orienteering_accounts.oris.client.ORISClient.get_event_additional_services',
            return_value={999999: [_service(999999, 'ZZZ0001')]},
        ):
            self.event.update_entries()

        self.assertEqual(self.event.entries.count(), 0)

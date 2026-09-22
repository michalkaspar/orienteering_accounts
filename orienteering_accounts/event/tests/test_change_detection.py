import copy
from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from orienteering_accounts.event.models import Event
from orienteering_accounts.event.tests import fixtures
from orienteering_accounts.oris import choices as oris_choices
from orienteering_accounts.oris.models import Event as OrisEvent


def _future_list_payload(**overrides):
    payload = copy.deepcopy(list(fixtures.ORIS_EVENTS_RESPONSE_DATA.values())[0])
    payload['Date'] = (timezone.now().date() + timedelta(days=7)).isoformat()
    payload.update(overrides)
    return {'Event_5712': payload}


class ChangeDetectionTestCase(TestCase):

    def setUp(self):
        entries_patcher = mock.patch('orienteering_accounts.event.models.Event.update_entries')
        self.update_entries_mock = entries_patcher.start()
        self.addCleanup(entries_patcher.stop)

        refresh_patcher = mock.patch('orienteering_accounts.event.models.Event._refresh_from_oris')
        self.refresh_from_oris_mock = refresh_patcher.start()
        self.addCleanup(refresh_patcher.stop)

        rate_patcher = mock.patch('orienteering_accounts.event.models.Event._update_exchange_rate')
        self.update_exchange_rate_mock = rate_patcher.start()
        self.addCleanup(rate_patcher.stop)

    def _import(self, payload):
        def fake_get_events(**kwargs):
            if kwargs['sport'] != oris_choices.SPORT_OB:
                return []
            return [OrisEvent(**item) for item in payload.values()]

        with mock.patch('orienteering_accounts.oris.client.ORISClient.get_events', side_effect=fake_get_events):
            Event.import_from_oris()

    def test_first_import_fetches_detail_and_entries(self):
        self._import(_future_list_payload())

        self.refresh_from_oris_mock.assert_called_once()
        self.update_entries_mock.assert_called_once()

    def test_unchanged_event_fetches_nothing(self):
        payload = _future_list_payload()
        self._import(payload)
        self.refresh_from_oris_mock.reset_mock()
        self.update_entries_mock.reset_mock()

        self._import(payload)

        self.refresh_from_oris_mock.assert_not_called()
        self.update_entries_mock.assert_not_called()

    def test_bumped_version_fetches_detail_only(self):
        self._import(_future_list_payload())
        self.refresh_from_oris_mock.reset_mock()
        self.update_entries_mock.reset_mock()

        self._import(_future_list_payload(Version='15'))

        self.refresh_from_oris_mock.assert_called_once()
        self.update_entries_mock.assert_not_called()

    def test_bumped_entry_timestamp_fetches_entries_only(self):
        self._import(_future_list_payload())
        self.refresh_from_oris_mock.reset_mock()
        self.update_entries_mock.reset_mock()

        self._import(_future_list_payload(ClubEntryLastModifiedTimeStamp=1769999999))

        self.update_entries_mock.assert_called_once()
        self.refresh_from_oris_mock.assert_not_called()

    def test_changed_entry_count_with_unchanged_timestamp_is_detected(self):
        self._import(_future_list_payload())
        self.update_entries_mock.reset_mock()

        self._import(_future_list_payload(ClubEntryCount='4'))

        self.update_entries_mock.assert_called_once()

    def test_changed_service_count_fetches_entries(self):
        self._import(_future_list_payload())
        self.update_entries_mock.reset_mock()

        self._import(_future_list_payload(ClubServiceEntryCount='2'))

        self.update_entries_mock.assert_called_once()

    def test_past_event_is_not_entry_synced(self):
        payload = copy.deepcopy(list(fixtures.ORIS_EVENTS_RESPONSE_DATA.values())[0])
        payload['Date'] = (timezone.now().date() - timedelta(days=3)).isoformat()

        self._import({'Event_5712': payload})

        self.refresh_from_oris_mock.assert_called_once()
        self.update_entries_mock.assert_not_called()


class RelayHandledTestCase(TestCase):

    def test_relay_handled_check_makes_no_oris_request(self):
        from django.conf import settings
        from model_bakery import baker

        event = baker.make(
            'event.Event',
            discipline={'oris_id': settings.ORIS_RELAY_RACE_IDS[0]},
            oris_club_entry_count=2,
            handled=False,
            handled_disabled=False,
        )

        with mock.patch('orienteering_accounts.oris.client.ORISClient.make_get_request') as request_mock:
            self.assertTrue(event.should_be_handled())

        request_mock.assert_not_called()

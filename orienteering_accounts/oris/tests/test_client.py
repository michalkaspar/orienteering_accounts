from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from requests.exceptions import HTTPError

from orienteering_accounts.oris import client as oris_client
from orienteering_accounts.oris.client import ORISClient
from orienteering_accounts.oris.tests import fixtures


def _response(status_code, headers=None, json_data=None):
    response = mock.Mock()
    response.status_code = status_code
    response.headers = headers or {}
    response.json.return_value = json_data or {'Data': {}}
    response.raise_for_status.side_effect = (
        HTTPError(f'{status_code} Client Error') if status_code >= 400 else None
    )
    return response


class ORISClientRetryTestCase(TestCase):

    def setUp(self):
        sleep_patcher = mock.patch('orienteering_accounts.oris.client.time.sleep')
        self.sleep_mock = sleep_patcher.start()
        self.addCleanup(sleep_patcher.stop)

    def test_retries_throttled_request_until_it_succeeds(self):
        request_func = mock.Mock(side_effect=[_response(429), _response(429), _response(200)])

        response = ORISClient.request_with_retry(request_func, 'https://oris.example.com/API/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(request_func.call_count, 3)
        self.assertEqual([call.args[0] for call in self.sleep_mock.call_args_list], [2, 4])

    def test_does_not_retry_successful_request(self):
        request_func = mock.Mock(return_value=_response(200))

        ORISClient.request_with_retry(request_func, 'https://oris.example.com/API/')

        self.assertEqual(request_func.call_count, 1)
        self.sleep_mock.assert_not_called()

    def test_does_not_retry_other_error_responses(self):
        request_func = mock.Mock(return_value=_response(404))

        response = ORISClient.request_with_retry(request_func, 'https://oris.example.com/API/')

        self.assertEqual(response.status_code, 404)
        self.assertEqual(request_func.call_count, 1)

    def test_gives_up_after_max_attempts(self):
        request_func = mock.Mock(return_value=_response(429))

        response = ORISClient.request_with_retry(request_func, 'https://oris.example.com/API/')

        self.assertEqual(response.status_code, 429)
        self.assertEqual(request_func.call_count, oris_client.ORIS_API_MAX_ATTEMPTS)
        self.assertEqual(self.sleep_mock.call_count, oris_client.ORIS_API_MAX_ATTEMPTS - 1)

    def test_respects_retry_after_header(self):
        request_func = mock.Mock(side_effect=[_response(429, headers={'Retry-After': '7'}), _response(200)])

        ORISClient.request_with_retry(request_func, 'https://oris.example.com/API/')

        self.sleep_mock.assert_called_once_with(7)

    def test_caps_retry_after_header(self):
        request_func = mock.Mock(side_effect=[_response(429, headers={'Retry-After': '3600'}), _response(200)])

        ORISClient.request_with_retry(request_func, 'https://oris.example.com/API/')

        self.sleep_mock.assert_called_once_with(oris_client.ORIS_API_RETRY_MAX_DELAY_SECONDS)

    def test_make_request_retries_throttled_request(self):
        with mock.patch('orienteering_accounts.oris.client.requests.get') as get_mock:
            get_mock.side_effect = [_response(429), _response(200, json_data={'Data': {'foo': 'bar'}})]

            data = ORISClient.make_get_request('getEventServiceEntries', params={'eventid': 1})

        self.assertEqual(data, {'foo': 'bar'})
        self.assertEqual(get_mock.call_count, 2)

    def test_make_request_raises_when_throttling_does_not_stop(self):
        with mock.patch('orienteering_accounts.oris.client.requests.get') as get_mock:
            get_mock.return_value = _response(429)

            with self.assertRaises(HTTPError):
                ORISClient.make_get_request('getEventServiceEntries', params={'eventid': 1})

        self.assertEqual(get_mock.call_count, oris_client.ORIS_API_MAX_ATTEMPTS)


class ClubMembersCacheTestCase(TestCase):

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.response_data = fixtures.club_user_list_response(
            fixtures.club_member_payload(390, 11, 'TZL6666', 'chuck@example.com'),
            fixtures.club_member_payload(377, 12, 'TZL9999', 'rocky@example.com'),
        )

    def test_roster_is_fetched_once_for_repeated_lookups(self):
        with mock.patch.object(ORISClient, 'make_get_request', return_value=self.response_data) as request_mock:
            first = ORISClient.get_club_member(390)
            second = ORISClient.get_club_member(377)

        self.assertEqual(request_mock.call_count, 1)
        self.assertEqual(first.email, 'chuck@example.com')
        self.assertEqual(second.email, 'rocky@example.com')

    def test_unknown_member_returns_none(self):
        with mock.patch.object(ORISClient, 'make_get_request', return_value=self.response_data):
            self.assertIsNone(ORISClient.get_club_member(999))

    def test_empty_response_is_not_cached(self):
        with mock.patch.object(ORISClient, 'make_get_request', return_value={}) as request_mock:
            ORISClient.get_club_member(390)
            ORISClient.get_club_member(390)

        self.assertEqual(request_mock.call_count, 2)

    def test_setting_entry_rights_invalidates_the_roster(self):
        with mock.patch.object(ORISClient, 'make_get_request', return_value=self.response_data) as request_mock:
            ORISClient.set_club_entry_rights(390, 11, can_entry_self=True)
            ORISClient.get_club_member(390)

        # roster, setClubEntryRights, roster again
        self.assertEqual(request_mock.call_count, 3)


class RegisteredUsersCacheTestCase(TestCase):

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.response_data = {
            'Reg_1': {
                'RegNo': 'TZL6666', 'UserID': '390', 'Lic': 'C', 'FirstName': 'Chuck',
                'LastName': 'Norris', 'SI': '7207026', 'Paid': '1', 'ClubID': 1,
                'Gender': 'M', 'Born': '70', 'Fee': '60',
            },
        }

    def test_registrations_are_fetched_once_per_sport_and_year(self):
        with mock.patch.object(ORISClient, 'make_get_request', return_value=self.response_data) as request_mock:
            ORISClient.get_registered_users(year=2026, sport=1)
            ORISClient.get_registered_users(year=2026, sport=1, licence='C')

        self.assertEqual(request_mock.call_count, 1)

    def test_different_sport_is_fetched_separately(self):
        with mock.patch.object(ORISClient, 'make_get_request', return_value=self.response_data) as request_mock:
            ORISClient.get_registered_users(year=2026, sport=1)
            ORISClient.get_registered_users(year=2026, sport=3)

        self.assertEqual(request_mock.call_count, 2)

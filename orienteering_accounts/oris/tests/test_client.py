from unittest import mock

from django.test import TestCase
from requests.exceptions import HTTPError

from orienteering_accounts.oris import client as oris_client
from orienteering_accounts.oris.client import ORISClient


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

from unittest import mock

from django.test import TestCase

from orienteering_accounts.event.models import Event
from orienteering_accounts.event.tests import fixtures


class ImportTestCase(TestCase):

    @mock.patch('orienteering_accounts.event.models.Event.update_entries')
    @mock.patch('orienteering_accounts.event.models.Event._update_exchange_rate')
    @mock.patch('orienteering_accounts.event.models.Event._refresh_from_oris')
    @mock.patch('orienteering_accounts.oris.client.ORISClient.make_get_request',
                return_value=fixtures.ORIS_EVENTS_RESPONSE_DATA)
    def test_import_events_from_oris(self, mock_get_events, mock_refresh, mock_exchange_rate, mock_update_entries):
        Event.import_from_oris()

        mock_get_events.assert_called()
        self.assertEqual(Event.objects.count(), 1)

from unittest import mock

from django.test import TestCase
from django.core.management import call_command

from orienteering_accounts.event.models import Event
from orienteering_accounts.event.tests import fixtures


class ImportTestCase(TestCase):

    @mock.patch('orienteering_accounts.oris.client.ORISClient.make_get_request',
                return_value=fixtures.ORIS_EVENTS_RESPONSE_DATA)
    def test_import_events_from_oris(self, mock_get_events):
        call_command('import_events_from_oris')
        mock_get_events.assert_called()
        self.assertEquals(Event.objects.count(), 1)

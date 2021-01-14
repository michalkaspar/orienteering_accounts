from datetime import datetime, timedelta
from unittest import mock

from django.conf import settings
from django.test import TestCase
from django.core.management import call_command

from orienteering_accounts.event.models import Event
from orienteering_accounts.event.tests import fixtures


class RefreshTestCase(TestCase):

    def test_refresh_event_from_oris(self):
        with mock.patch('orienteering_accounts.oris.client.ORISClient.make_get_request',
                        return_value=fixtures.ORIS_EVENTS_RESPONSE_DATA):

            call_command('import_events_from_oris')
            self.assertEqual(Event.objects.count(), 1)
            event = Event.objects.first()
            event.date = datetime.today() - timedelta(days=settings.REFRESH_EVENTS_BEFORE_DAYS - 1)
            event.save()

            with mock.patch('orienteering_accounts.oris.client.ORISClient.make_get_request',
                            return_value=fixtures.ORIS_EVENT_RESPONSE_DATA) as mock_get_event_request:

                # TODO mock get event entries
                pass
                #call_command('refresh_events_from_oris')
                #mock_get_event_request.assert_called()
                #event.refresh_from_db()
                #self.assertIsNotNone(event.categories_data)
                ## TODO update when there will be more data processing in update
                #self.assertNotEqual(event.categories_data, {})

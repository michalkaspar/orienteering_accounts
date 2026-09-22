from unittest import mock

from django.test import TestCase

from orienteering_accounts.event.models import Event
from orienteering_accounts.event.tests import fixtures
from orienteering_accounts.oris.models import Event as OrisEvent


class ClubMarkersTestCase(TestCase):

    def test_list_payload_populates_club_markers(self):
        payload = list(fixtures.ORIS_EVENTS_RESPONSE_DATA.values())[0]

        event = Event.upsert_from_oris(OrisEvent(**payload))

        self.assertEqual(event.oris_club_entry_count, 3)
        self.assertEqual(event.oris_club_entry_last_modified_timestamp, 1769371100)
        self.assertEqual(event.oris_club_service_entry_count, 1)
        self.assertEqual(event.oris_club_service_entry_last_modified_timestamp, 1769371200)

    def test_detail_refresh_does_not_wipe_club_markers(self):
        list_payload = list(fixtures.ORIS_EVENTS_RESPONSE_DATA.values())[0]
        event = Event.upsert_from_oris(OrisEvent(**list_payload))

        with mock.patch('orienteering_accounts.oris.client.ORISClient.make_get_request',
                        return_value=fixtures.ORIS_EVENT_RESPONSE_DATA):
            event._refresh_from_oris()

        event.refresh_from_db()
        self.assertEqual(event.oris_club_entry_count, 3)
        self.assertEqual(event.oris_club_entry_last_modified_timestamp, 1769371100)

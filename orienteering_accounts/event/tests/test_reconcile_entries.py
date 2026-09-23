from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone
from model_bakery import baker

from orienteering_accounts.event.models import Event


class ReconcileEntriesTestCase(TestCase):

    def setUp(self):
        patcher = mock.patch('orienteering_accounts.event.models.Event.update_entries')
        self.update_entries_mock = patcher.start()
        self.addCleanup(patcher.stop)

        # Step 4b's detail-refresh loop shares the same querysets as these
        # entry-reconciliation tests (e.g. the far-future event is also
        # handled and UNPROCESSED), so it gets touched too. Silence it here
        # so these tests stay unit tests instead of making real HTTP calls.
        refresh_patcher = mock.patch('orienteering_accounts.event.models.Event._refresh_from_oris')
        refresh_patcher.start()
        self.addCleanup(refresh_patcher.stop)

    def _event(self, **overrides):
        defaults = {
            'handled': True,
            'date': timezone.now().date() + timedelta(days=7),
            'entries_synced_at': timezone.now(),
        }
        defaults.update(overrides)
        return baker.make('event.Event', **defaults)

    def test_recently_synced_event_is_skipped(self):
        self._event()

        Event.reconcile_entries_from_oris()

        self.update_entries_mock.assert_not_called()

    def test_stale_event_is_resynced(self):
        self._event(entries_synced_at=timezone.now() - timedelta(hours=25))

        Event.reconcile_entries_from_oris()

        self.update_entries_mock.assert_called_once()

    def test_never_synced_event_is_resynced(self):
        self._event(entries_synced_at=None)

        Event.reconcile_entries_from_oris()

        self.update_entries_mock.assert_called_once()

    def test_unhandled_event_is_skipped(self):
        self._event(handled=False, entries_synced_at=None)

        Event.reconcile_entries_from_oris()

        self.update_entries_mock.assert_not_called()

    def test_past_event_is_skipped(self):
        self._event(date=timezone.now().date() - timedelta(days=1), entries_synced_at=None)

        Event.reconcile_entries_from_oris()

        self.update_entries_mock.assert_not_called()

    def test_far_future_event_beyond_the_list_window_is_covered(self):
        self._event(date=timezone.now().date() + timedelta(days=300), entries_synced_at=None)

        Event.reconcile_entries_from_oris()

        self.update_entries_mock.assert_called_once()


class ReconcileDetailRefreshTestCase(TestCase):
    """Step 4b: handled events beyond the list window still get a detail refresh."""

    def setUp(self):
        entries_patcher = mock.patch('orienteering_accounts.event.models.Event.update_entries')
        self.update_entries_mock = entries_patcher.start()
        self.addCleanup(entries_patcher.stop)

        refresh_patcher = mock.patch('orienteering_accounts.event.models.Event._refresh_from_oris')
        self.refresh_from_oris_mock = refresh_patcher.start()
        self.addCleanup(refresh_patcher.stop)

    def _event(self, **overrides):
        defaults = {
            'handled': True,
            'processing_state': Event.ProcessingType.UNPROCESSED,
            'date': timezone.now().date() + timedelta(days=7),
            'entries_synced_at': timezone.now(),
        }
        defaults.update(overrides)
        return baker.make('event.Event', **defaults)

    def test_handled_event_beyond_window_gets_detail_refreshed(self):
        self._event(date=timezone.now().date() + timedelta(days=300))

        Event.reconcile_entries_from_oris()

        self.refresh_from_oris_mock.assert_called_once()

    def test_handled_event_inside_window_is_not_refreshed_here(self):
        self._event(date=timezone.now().date() + timedelta(days=7))

        Event.reconcile_entries_from_oris()

        self.refresh_from_oris_mock.assert_not_called()

from django.test import TestCase
from django.urls import reverse

from orienteering_accounts.core.changelog_data import CHANGELOG_ENTRIES


class ChangelogViewTestCase(TestCase):

    def test_changelog_page_renders_for_anonymous_user(self):
        response = self.client.get(reverse('changelog'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/changelog.html')

    def test_changelog_entries_passed_in_context_sorted_newest_first(self):
        response = self.client.get(reverse('changelog'))

        dates = [entry['date'] for entry in response.context['changelog_entries']]

        self.assertEqual(dates, sorted(dates, reverse=True))
        self.assertEqual(len(response.context['changelog_entries']), len(CHANGELOG_ENTRIES))

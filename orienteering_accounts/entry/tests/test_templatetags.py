from django.test import TestCase

from orienteering_accounts.entry.models import Entry
from orienteering_accounts.entry.templatetags.entry import entry_additional_service_value


class EntryAdditionalServiceValueTestCase(TestCase):

    def test_sums_duplicate_service_id_entries(self):
        entry = Entry(additional_services=[
            {'Service': {'ID': 1, 'NameCZ': 'Ubytování v kempu'}, 'TotalFee': '1500'},
            {'Service': {'ID': 1, 'NameCZ': 'Ubytování v kempu'}, 'TotalFee': '300'},
        ])

        value = entry_additional_service_value(entry, {'ID': 1})

        self.assertEqual(value, 1800)

    def test_returns_dash_when_service_not_ordered(self):
        entry = Entry(additional_services=[
            {'Service': {'ID': 1, 'NameCZ': 'Tricko'}, 'TotalFee': '100'},
        ])

        value = entry_additional_service_value(entry, {'ID': 2})

        self.assertEqual(value, '-')

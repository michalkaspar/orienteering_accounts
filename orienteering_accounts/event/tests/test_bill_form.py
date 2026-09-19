from decimal import Decimal

from django.test import TestCase
from model_bakery import baker

from orienteering_accounts.entry.models import Entry
from orienteering_accounts.event.forms import EntryBillForm


class EntryBillFormTestCase(TestCase):

    def setUp(self):
        self.entry = baker.make(Entry, fee=200, additional_services=[], debt=Decimal(200))

    def _form(self, **data):
        form_data = {'debt': '200', 'other_debt': '', 'debt_note': ''}
        form_data.update(data)
        return EntryBillForm(form_data, instance=self.entry)

    def test_blank_other_debt_is_valid(self):
        form = self._form(other_debt='')
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.cleaned_data['other_debt'])

    def test_other_debt_without_note_is_invalid(self):
        form = self._form(other_debt='50', debt_note='')
        self.assertFalse(form.is_valid())
        self.assertIn('debt_note', form.errors)

    def test_other_debt_with_note_is_valid(self):
        form = self._form(other_debt='50', debt_note='Pujceny cip')
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['other_debt'], Decimal(50))

    def test_invalid_other_debt_does_not_break_note_validation(self):
        form = self._form(other_debt='abc', debt_note='')
        self.assertFalse(form.is_valid())
        self.assertIn('other_debt', form.errors)

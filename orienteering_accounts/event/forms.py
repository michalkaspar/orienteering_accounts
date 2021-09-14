from decimal import Decimal

from django import forms
from datetime import date

from django.forms import modelformset_factory

from orienteering_accounts.account.models import Account, Transaction
from orienteering_accounts.entry.models import Entry
from orienteering_accounts.event.models import Event


class EventForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def read_only(self):
        return self.instance.date <= date.today()

    def is_valid(self):
        if not super().is_valid():
            return False
        return self.instance.handled or self.instance.leader is None

    class Meta:
        model = Event
        fields = ['handled', 'leader']


class EntryBillForm(forms.ModelForm):

    class Meta:
        models = Entry
        fields = ('debt',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.initial['debt'] = self.instance.debt_init

    def save(self, *args, **kwargs):
        entry = super().save(*args, **kwargs)
        if entry.debt > Decimal(0):
            entry.transactions.create(
                purpose=Transaction.TransactionPurpose.ENTRY,
                account=entry.account,
                amount=-entry.debt
            )
        return entry


EventEntryBillFormSet = modelformset_factory(Entry, fields=['debt'], form=EntryBillForm, extra=0)

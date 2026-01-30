from decimal import Decimal

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, ButtonHolder, Submit
from django import forms
from datetime import date

from django.core.exceptions import ValidationError
from django.forms import modelformset_factory

from orienteering_accounts.account.models import Account, Transaction
from orienteering_accounts.entry.models import Entry
from orienteering_accounts.event.models import Event


class EventForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['leader'].queryset = Account.objects.order_by('-leader_priority', 'last_name', 'first_name')
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'handled',
            'leader',
            ButtonHolder(
                Submit('save', 'Uložit', css_class='btn btn-success'),
                css_class="modal-footer"
            )
        )

    def read_only(self):
        return self.instance.date <= date.today()

    def is_valid(self):
        if not super().is_valid():
            return False
        return self.instance.handled or self.instance.leader is None

    def save(self, commit=True):
        if 'handled' in self.changed_data and not self.cleaned_data['handled']:
            self.instance.handled_disabled = True
        return super().save(commit=commit)

    class Meta:
        model = Event
        fields = ['handled', 'leader']


class EntryBillForm(forms.ModelForm):

    class Meta:
        models = Entry
        fields = ('debt', 'other_debt', 'debt_note')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            if self.instance.debt:
                self.initial['debt'] = self.instance.debt
            else:
                self.initial['debt'] = self.instance.debt_init

                if not (self.instance.event.is_stage or self.instance.is_multi_stage) and self.instance.event.did_not_start(self.instance.account.registration_number):
                    self.initial['debt_note'] = 'Neúčast na závodě.'

            if not self.instance.other_debt:
                self.initial['other_debt'] = Decimal(0)

    def clean_debt_note(self):
        other_debt = self.cleaned_data['other_debt']
        debt_note = self.cleaned_data['debt_note']
        if other_debt and not debt_note:
            raise ValidationError("Je nutné vyplnit poznámku, pokud jsou vyplněny další náklady.")

        return debt_note

    def clean_debt(self):
        debt = self.cleaned_data['debt']
        if debt - self.instance.additional_services_cost_sum < Decimal(0):
            raise ValidationError("Dluh nemůže být nižší než součet doplňkových služeb.")
        return debt

    def save(self, *args, **kwargs):
        entry = super().save(*args, **kwargs)
        entry.transactions.update_or_create(
            purpose=Transaction.TransactionPurpose.ENTRY,
            account=entry.account,
            defaults=dict(
                amount=-(entry.debt - entry.additional_services_cost_sum),
                is_future=False,
                author_name=entry.event.leader.full_name if entry.event.leader else ''
            ),
        )
        if entry.other_debt and entry.other_debt > Decimal(0):
            entry.transactions.update_or_create(
                purpose=Transaction.TransactionPurpose.ENTRY_OTHER,
                account=entry.account,
                defaults=dict(
                    amount=-entry.other_debt,
                    note=entry.debt_note,
                    author_name=entry.event.leader.full_name if entry.event.leader else ''
                )
            )
        else:
            # Case when other debt is deleted
            entry.transactions.filter(
                purpose=Transaction.TransactionPurpose.ENTRY_OTHER,
                account=entry.account
            ).exclude(
                author_name="System"
            ).delete()

        # Additional services
        entry.transactions.filter(
            purpose=Transaction.TransactionPurpose.ENTRY_OTHER,
            account=entry.account,
            author_name="System"
        ).update(
            is_future=False
        )

        return entry


EventEntryBillFormSet = modelformset_factory(Entry, fields=['debt', 'other_debt', 'debt_note'], form=EntryBillForm, extra=0)

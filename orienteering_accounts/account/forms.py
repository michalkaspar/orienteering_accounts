from decimal import Decimal

from django import forms
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import ugettext_lazy as _

from orienteering_accounts.account.models import Transaction


class TransactionAddForm(forms.ModelForm):

    class TransactionType(models.TextChoices):
        COST = 'COST', _('Výdaj')
        INCOME = 'INCOME', _('Příjem')

    transaction_type = forms.ChoiceField(choices=TransactionType.choices, initial=TransactionType.COST, label=_('Typ transakce'))

    class Meta:
        model = Transaction
        fields = ['amount', 'note', 'account', 'purpose']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['note'].required = True
        self.fields['amount'].validators = [MinValueValidator(Decimal(0))]

    def clean(self):
        if self.cleaned_data['transaction_type'] == TransactionAddForm.TransactionType.COST:
            self.cleaned_data['amount'] *= -1
        return super().clean()

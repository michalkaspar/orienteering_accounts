from decimal import Decimal

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.validators import MinValueValidator
from django.db import models
from django.forms import ModelForm
from django.utils.translation import ugettext_lazy as _

from orienteering_accounts.account.models import Transaction, Role, Permission, Account, PaymentPeriod


class LoginForm(AuthenticationForm):
    def __init__(self, request=None, *args, **kwargs):
        super(LoginForm, self).__init__(request=request, *args, **kwargs)


class PaymentPeriodForm(forms.ModelForm):

    class Meta:
        model = PaymentPeriod
        fields = ['date_from', 'date_to']
        widgets = {
            'date_from': forms.DateInput(attrs={'class':'form-control', 'type':'date'}),
            'date_to': forms.DateInput(attrs={'class':'form-control', 'type':'date'})
        }


class TransactionAddForm(forms.ModelForm):

    class TransactionType(models.TextChoices):
        COST = 'COST', _('Výdaj')
        INCOME = 'INCOME', _('Příjem')

    transaction_type = forms.ChoiceField(choices=TransactionType.choices, initial=TransactionType.COST, label=_('Typ transakce'))

    class Meta:
        model = Transaction
        fields = ['amount', 'note', 'account', 'purpose', 'period']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['note'].required = True
        self.fields['amount'].validators = [MinValueValidator(Decimal(0))]

    def clean(self):
        cleaned_data = super().clean()

        if cleaned_data['purpose'] == Transaction.TransactionPurpose.CLUB_MEMBERSHIP and not cleaned_data['period']:
            self.add_error('period', _('Je nutné zvolit období pro platbu v případě oddílového příspěvku'))

        if self.cleaned_data['transaction_type'] == TransactionAddForm.TransactionType.COST:
            self.cleaned_data['amount'] *= -1

        return cleaned_data


class AccountEditForm(ModelForm):

    class Meta:
        model = Account
        fields = ['role']


class RoleForm(ModelForm):
    permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.all(),
        widget=forms.CheckboxSelectMultiple(),
        label=_('Práva'),
        required=False
    )

    class Meta:
        model = Role
        fields = ['name', 'permissions']

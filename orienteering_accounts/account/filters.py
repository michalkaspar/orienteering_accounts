import django_filters
from django import forms

from orienteering_accounts.account.models import Account, Transaction
from django.utils.translation import ugettext_lazy as _


class AccountFilter(django_filters.FilterSet):
    registration_number = django_filters.CharFilter(
        field_name='registration_number',
        lookup_expr='icontains',
        label=_('Registrační číslo')
    )
    last_name = django_filters.CharFilter(
        field_name='last_name',
        lookup_expr='icontains',
        label=_('Příjmení')
    )
    club_membership_paid = django_filters.BooleanFilter(
        field_name='club_membership_paid',
        method='filter_club_membership_paid',
        widget=forms.CheckboxInput,
        label=_('Zaplatil příspěvky')
    )
    debts_paid = django_filters.BooleanFilter(
        field_name='debts_paid',
        method='filter_debts_paid',
        widget=forms.CheckboxInput,
        label=_('Zaplatil dluhy')
    )

    class Meta:
        model = Account
        fields = ['registration_number', 'last_name', 'debts_paid', 'club_membership_paid']

    @property
    def qs(self):
        return super().qs.distinct().order_by('last_name')

    def filter_club_membership_paid(self, queryset, name, value):
        if value:
            return queryset.filter(transactions__purpose=Transaction.TransactionPurpose.CLUB_MEMBERSHIP)
        return queryset

    def filter_debts_paid(self, queryset, name, value):
        if value:
            return queryset.filter(transactions__purpose=Transaction.TransactionPurpose.DEBTS)
        return queryset

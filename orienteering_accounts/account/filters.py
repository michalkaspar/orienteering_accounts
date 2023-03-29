import django_filters
from django import forms
from django.db.models import Sum, Q, F, Max
from django.db.models.functions import Coalesce

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
    first_name = django_filters.CharFilter(
        field_name='first_name',
        lookup_expr='icontains',
        label=_('Křestní jméno')
    )
    email = django_filters.CharFilter(
        field_name='email',
        lookup_expr='icontains',
        label=_('Email')
    )
    is_active = django_filters.BooleanFilter(
        field_name='is_active',
        label=_('Aktivní')
    )

    class Meta:
        model = Account
        fields = ['registration_number', 'first_name', 'last_name', 'email', 'is_active']

    def __init__(self, data=None, *args, **kwargs):
        super().__init__(data, queryset=Account.all_objects.all(), *args, **kwargs)

    @property
    def qs(self):
        queryset = super().qs.distinct()

        if 'is_active' not in self.request.GET:
            queryset = queryset.filter(is_active=True)

        queryset = queryset.annotate(
            membership_paid_to=Max(
                'transactions__period__date_to', filter=Q(
                    transactions__purpose=Transaction.TransactionPurpose.CLUB_MEMBERSHIP
                )
            )
        )
        if 'o' in self.request.GET:
            ordering = self.request.GET['o']

            if 'balance' in ordering:
                queryset = queryset.annotate(
                    balance_=F('init_balance') + Coalesce(Sum(
                        'transactions__amount',
                        filter=~Q(transactions__purpose=Transaction.TransactionPurpose.CLUB_MEMBERSHIP)
                    ), 0)
                ).order_by(f'{"-" if "-" in ordering else ""}balance_')
            else:
                queryset = queryset.order_by(ordering)
        else:
            queryset = queryset.order_by('last_name')

        return queryset

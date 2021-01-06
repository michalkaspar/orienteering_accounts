import django_filters

from orienteering_accounts.account.models import Account


class AccountFilter(django_filters.FilterSet):

    class Meta:
        model = Account
        fields = ['registration_number', 'first_name', 'last_name']

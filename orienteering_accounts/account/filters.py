import django_filters

from orienteering_accounts.account.models import Account
from django.utils.translation import ugettext_lazy as _


class AccountFilter(django_filters.FilterSet):
    registration_number = django_filters.CharFilter(field_name='registration_number', lookup_expr='icontains', label=_('Registrační číslo'))
    last_name = django_filters.CharFilter(field_name='last_name', lookup_expr='icontains', label=_('Příjmení'))

    class Meta:
        model = Account
        fields = ['registration_number', 'last_name']

    @property
    def qs(self):
        return super().qs.order_by('last_name')

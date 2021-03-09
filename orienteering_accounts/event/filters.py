import django_filters

from orienteering_accounts.event.models import Event
from django.utils.translation import ugettext_lazy as _


class EventFilter(django_filters.FilterSet):
    # date = django_filters.DateFromToRangeFilter(field_name='date', label=_('Datum'))
    date_from = django_filters.DateFilter(field_name='date', lookup_expr='gte', label=_('Datum od'))
    date_to = django_filters.DateFilter(field_name='date', lookup_expr='lte', label=_('Datum do'))
    region = django_filters.CharFilter(field_name='region', lookup_expr='icontains', label=_('Oblast'))
    handled = django_filters.BooleanFilter(field_name='handled', label=_('Zpracované?'))
    leader = django_filters.BooleanFilter(field_name='leader', method='filter_leader', label=_('Vedoucí?'))

    def filter_leader(self, qs, fname, value):
        lookup = '__'.join([fname, 'isnull'])
        return qs.filter(**{lookup: not value})

    class Meta:
        model = Event
        # fields = ['date', 'region', 'handled']
        fields = ['date_from', 'date_to', 'region', 'handled', 'leader']

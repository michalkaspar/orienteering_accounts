import django_filters
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, ButtonHolder, Submit

from orienteering_accounts.event.models import Event
from django.utils.translation import ugettext_lazy as _


class EventFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(field_name='name', lookup_expr='icontains', label=_('Název'))
    date_from = django_filters.DateFilter(field_name='date', lookup_expr='gte', label=_('Datum od'))
    date_to = django_filters.DateFilter(field_name='date', lookup_expr='lte', label=_('Datum do'))
    region = django_filters.CharFilter(field_name='region', lookup_expr='icontains', label=_('Oblast'))
    handled = django_filters.BooleanFilter(field_name='handled', label=_('Zpracované?'))
    leader = django_filters.BooleanFilter(field_name='leader', method='filter_leader', label=_('Vedoucí?'))
    bills_solved = django_filters.BooleanFilter(field_name='bills_solved', label=_('Dluhy vyplněny?'))

    def __init__(self, data=None, *args, **kwargs):
        if data is None:
            data = dict(handled=True)

        super().__init__(data, *args, **kwargs)
        self.form.helper = FormHelper()
        self.form.helper.form_method = 'GET'
        self.form.helper.layout = Layout(
            'date_from',
            'date_to',
            'region',
            'handled',
            'leader',
            'bills_solved',
            'name',
            ButtonHolder(
                Submit('search', 'Hledat', css_class='btn btn-success'),
                css_class="modal-footer"
            )
        )

    def filter_leader(self, qs, fname, value):
        lookup = '__'.join([fname, 'isnull'])
        return qs.filter(**{lookup: not value})

    class Meta:
        model = Event
        fields = ['date_from', 'date_to', 'region', 'handled', 'leader', 'bills_solved']

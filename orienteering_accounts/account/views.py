from django_filters.views import FilterView
from orienteering_accounts.account.filters import AccountFilter


class AccountList(FilterView):
    template_name = 'account/list.html'
    filterset_class = AccountFilter


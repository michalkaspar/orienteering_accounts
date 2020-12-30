from django.views.generic import ListView

from orienteering_accounts.account.models import Account


class AccountList(ListView):
    template_name = 'account/list.html'
    queryset = Account.objects.all()

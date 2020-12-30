from django.urls import path

from orienteering_accounts.account.views import AccountList

app_name = 'accounts'

urlpatterns = [
    path('', AccountList.as_view(), name='list'),
]

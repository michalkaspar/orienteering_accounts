from django.urls import path

from orienteering_accounts.account.views import AccountList, AccountDetail, TransactionCreate

app_name = 'accounts'

urlpatterns = [
    path('', AccountList.as_view(), name='list'),
    path('<int:pk>/', AccountDetail.as_view(), name='detail'),
    path('<int:pk>/transaction/add/', TransactionCreate.as_view(), name='transaction_add')
]

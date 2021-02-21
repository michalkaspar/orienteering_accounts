from django.urls import path, include

from orienteering_accounts.account.views import AccountList, AccountDetail, AccountEdit, TransactionCreate, RoleListView, \
    RoleAddView, RoleEditView

app_name = 'accounts'

role_urlpatterns = ([
    path('', RoleListView.as_view(), name='list'),
    path('add/', RoleAddView.as_view(), name='add'),
    path('<int:pk>/edit/', RoleEditView.as_view(), name='edit'),
], 'role')

urlpatterns = [
    path('', AccountList.as_view(), name='list'),
    path('role/', include(role_urlpatterns)),
    path('<int:pk>/', AccountDetail.as_view(), name='detail'),
    path('<int:pk>/edit/', AccountEdit.as_view(), name='edit'),
    path('<int:pk>/transaction/add/', TransactionCreate.as_view(), name='transaction_add')
]

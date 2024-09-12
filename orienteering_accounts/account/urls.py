from django.urls import path, include

from orienteering_accounts.account.views import (
    AccountListView, AccountExportView, AccountDetailView, AccountEditView, TransactionCreate, RoleListView,
    RoleAddView, RoleEditView, AccountTransactionsEmbeddedView, AccountTransactionsView, PaymentPeriodEditView,
    PaymentPeriodListView,
    PaymentPeriodCreateView, TransactionEdit, ClubroomChipNumberView, ClubroomChipNumberExportView,
    BankTransactionListView, AccountPasswordSetView
)

app_name = 'accounts'

role_urlpatterns = ([
    path('', RoleListView.as_view(), name='list'),
    path('add/', RoleAddView.as_view(), name='add'),
    path('<int:pk>/edit/', RoleEditView.as_view(), name='edit'),
], 'role')


payment_period_urlpatterns = ([
    path('', PaymentPeriodListView.as_view(), name='list'),
    path('add/', PaymentPeriodCreateView.as_view(), name='add'),
    path('<int:pk>/edit/', PaymentPeriodEditView.as_view(), name='edit'),
], 'payment_period')


urlpatterns = [
    path('', AccountListView.as_view(), name='list'),
    path('export/', AccountExportView.as_view(), name='export'),
    path('clubroom-chip-list/', ClubroomChipNumberView.as_view(), name='clubroom_chip_list'),
    path('clubroom-chip-list/export/', ClubroomChipNumberExportView.as_view(), name='clubroom_chip_list_export'),
    path('role/', include(role_urlpatterns)),
    path('payment_period/', include(payment_period_urlpatterns)),
    path('<int:pk>/', AccountDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', AccountEditView.as_view(), name='edit'),
    path('<int:pk>/password-change/', AccountPasswordSetView.as_view(), name='password_change'),
    path('<int:pk>/transaction/add/', TransactionCreate.as_view(), name='transaction_add'),
    path('transaction/<int:pk>/edit/', TransactionEdit.as_view(), name='transaction_edit'),
    path('transactions/', AccountTransactionsEmbeddedView.as_view(), name='embedded'),
    path('transactions/<uuid:key>/', AccountTransactionsView.as_view(), name='transactions'),
    path('bank-transactions/', BankTransactionListView.as_view(), name='bank_transactions'),
]

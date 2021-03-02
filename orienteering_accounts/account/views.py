from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import CreateView, DetailView, UpdateView, ListView, TemplateView
from django.utils.translation import ugettext_lazy as _
from django_filters.views import FilterView

from requests import HTTPError

from orienteering_accounts.account.filters import AccountFilter
from orienteering_accounts.account.forms import TransactionAddForm, AccountEditForm, PaymentPeriodForm
from orienteering_accounts.account.models import Transaction, Account, PaymentPeriod
from orienteering_accounts.account import perms
from orienteering_accounts.account.forms import RoleForm
from orienteering_accounts.account.models import Role


from django.contrib.auth.views import LoginView

from orienteering_accounts.account.forms import LoginForm
from orienteering_accounts.core.mixins import PermissionsRequiredMixin


class PaymentPeriodListView(LoginRequiredMixin, PermissionsRequiredMixin, ListView):
    template_name = 'account/payment_period/list.html'
    model = PaymentPeriod
    permissions_required = perms.payment_period_view_perms


class PaymentPeriodCreateView(LoginRequiredMixin, PermissionsRequiredMixin, CreateView):
    model = PaymentPeriod
    form_class = PaymentPeriodForm
    template_name = 'account/payment_period/create.html'
    permissions_required = perms.payment_period_create_perms

    def get_success_url(self):
        return reverse('accounts:payment_period:list')


class PaymentPeriodEditView(LoginRequiredMixin, PermissionsRequiredMixin, UpdateView):
    model = PaymentPeriod
    form_class = PaymentPeriodForm
    template_name = 'account/payment_period/edit.html'
    permissions_required = perms.payment_period_edit_perms

    def get_success_url(self):
        return reverse('accounts:payment_period:list')


class AccountLoginView(LoginView):
    form_class = LoginForm
    redirect_authenticated_user = True


class AccountListView(LoginRequiredMixin, PermissionsRequiredMixin, FilterView):
    template_name = 'account/list.html'
    filterset_class = AccountFilter
    permissions_required = perms.account_view_perms


class AccountDetailView(LoginRequiredMixin, PermissionsRequiredMixin, DetailView):
    model = Account
    template_name = 'account/detail.html'
    permissions_required = perms.account_view_perms


class AccountEditView(LoginRequiredMixin, PermissionsRequiredMixin, UpdateView):
    model = Account
    template_name = 'account/edit.html'
    permissions_required = perms.account_edit_perms
    form_class = AccountEditForm

    def get_success_url(self):
        return reverse('accounts:detail', args=[self.object.pk])


class TransactionCreate(LoginRequiredMixin, PermissionsRequiredMixin, CreateView):
    template_name = 'transaction/create.html'
    model = Transaction
    form_class = TransactionAddForm
    permissions_required = perms.transaction_create_perms

    def get_form(self, *args, **kwargs):
        form = super(TransactionCreate, self).get_form(*args, **kwargs)
        form.fields['account'].widget = forms.HiddenInput()
        form.fields['account'].required = False
        return form

    def get_initial(self):
        initial = super().get_initial()
        initial.update(
            account=self.kwargs['pk']
        )
        return initial

    def get_account(self):
        return get_object_or_404(Account, id=self.kwargs['pk'])

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        context_data.update(account=self.get_account())
        return context_data

    def form_valid(self, form):
        try:
            with transaction.atomic():
                created_transaction = form.save()
                account = created_transaction.account
                if created_transaction.purpose == Transaction.TransactionPurpose.CLUB_MEMBERSHIP and account.is_late_with_club_membership_payment:
                    account.add_entry_rights_in_oris()
                    account.is_late_with_club_membership_payment = False
                    account.save()
        except HTTPError:
            messages.add_message(
                self.request,
                messages.ERROR,
                _('Transakci nelze přidat, chyba při komunikaci s ORIS.')
            )

        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse('accounts:detail', args=[self.kwargs['pk']])


class AccountTransactionsView(TemplateView):
    template_name = 'account/transactions.html'

    def get_context_data(self, **kwargs):
        account = get_object_or_404(Account, id=self.kwargs['pk'])

        context_data = super().get_context_data(**kwargs)
        context_data.update(
            account=account
        )
        return context_data


class RoleListView(LoginRequiredMixin, PermissionsRequiredMixin, ListView):
    model = Role
    permissions_required = perms.role_view_perms
    template_name = 'account/role/list.html'


class RoleAddView(LoginRequiredMixin, PermissionsRequiredMixin, CreateView):
    model = Role
    permissions_required = perms.role_add_perms
    template_name = 'account/role/edit.html'
    form_class = RoleForm

    def get_success_url(self):
        return reverse('accounts:role:list')


class RoleEditView(LoginRequiredMixin, PermissionsRequiredMixin, UpdateView):
    model = Role
    permissions_required = perms.role_edit_perms
    template_name = 'account/role/edit.html'
    form_class = RoleForm

    def get_success_url(self):
        return reverse('accounts:role:list')

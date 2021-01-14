from django import forms
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import CreateView, DetailView
from django_filters.views import FilterView
from orienteering_accounts.account.filters import AccountFilter
from orienteering_accounts.account.forms import TransactionAddForm
from orienteering_accounts.account.models import Transaction, Account


class AccountList(FilterView):
    template_name = 'account/list.html'
    filterset_class = AccountFilter


class AccountDetail(DetailView):
    model = Account


class TransactionCreate(CreateView):
    template_name = 'transaction/create.html'
    model = Transaction
    form_class = TransactionAddForm

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

    def get_success_url(self):
        return reverse('accounts:detail', args=[self.kwargs['pk']])

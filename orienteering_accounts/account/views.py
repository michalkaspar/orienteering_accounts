from django import forms
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import CreateView, DetailView
from django_filters.views import FilterView
from django.utils.translation import ugettext_lazy as _
from requests import HTTPError

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

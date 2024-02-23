import io
import xlsxwriter
import jwt

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.db import transaction
from django.http import HttpResponseRedirect, HttpResponse, Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, DetailView, UpdateView, ListView, TemplateView
from django.utils.translation import ugettext_lazy as _, gettext
from django_filters.views import FilterView

from requests import HTTPError

from orienteering_accounts.account.filters import AccountFilter
from orienteering_accounts.account.forms import TransactionAddForm, AccountEditForm, PaymentPeriodForm, \
    TransactionEditForm, AccountPasswordChangeEditForm, AccountPasswordSetEditForm
from orienteering_accounts.account.models import Transaction, Account, PaymentPeriod
from orienteering_accounts.account import perms
from orienteering_accounts.account.forms import RoleForm
from orienteering_accounts.account.models import Role


from django.contrib.auth.views import LoginView

from orienteering_accounts.account.forms import LoginForm
from orienteering_accounts.core.mixins import PermissionsRequiredMixin
from orienteering_accounts.core.models import ChangeLog


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

    def get_context_data(self, *, object_list=None, **kwargs):
        context_data = super().get_context_data(object_list=object_list, **kwargs)
        if 'o' in self.request.GET:
            ordering = self.request.GET['o']
            if ordering.startswith('-'):
                context_data.update(descendant=False)
            else:
                context_data.update(descendant=True)
            context_data.update(ordering=ordering)
        return context_data


class AccountExportView(LoginRequiredMixin, PermissionsRequiredMixin, View):
    permissions_required = perms.account_view_perms

    def get(self, *args, **kwargs):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet()

        worksheet.set_column(0, 0, width=20)
        worksheet.set_column(0, 1, width=20)
        worksheet.set_column(0, 2, width=20)
        worksheet.set_column(0, 3, width=20)

        worksheet.write(0, 0, gettext('Jméno a Příjmení'))
        worksheet.write(0, 1, gettext('Registrační číslo'))
        worksheet.write(0, 2, gettext('Příspěvky uhrazeny'))
        worksheet.write(0, 3, gettext('Dluhy uhrazeny'))

        for i, account in enumerate(Account.objects.order_by('last_name')):

            row = i+1

            worksheet.write(row, 0, account.full_name_inv)
            worksheet.write(row, 1, account.registration_number)
            worksheet.write(row, 2, gettext('ANO') if account.club_membership_paid else gettext('NE'))
            worksheet.write(row, 3, gettext('ANO') if account.debts_paid else gettext('NE'))

        worksheet.fit_to_pages(1, 0)
        workbook.close()
        output.seek(0)

        response = HttpResponse(
            ContentFile(output.read()),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename=accounts.xlsx'

        return response


class AccountDetailView(LoginRequiredMixin, PermissionsRequiredMixin, DetailView):
    queryset = Account.all_objects.all()
    template_name = 'account/detail.html'
    permissions_required = perms.account_view_perms


class AccountEditView(LoginRequiredMixin, PermissionsRequiredMixin, UpdateView):
    queryset = Account.all_objects.all()
    template_name = 'account/edit.html'
    permissions_required = perms.account_edit_perms

    def get_success_url(self):
        return reverse('accounts:detail', args=[self.object.pk])

    def get_form_class(self):
        if self.request.user.pk == self.object.pk:
            return AccountPasswordChangeEditForm
        if self.request.user.is_superuser:
            return AccountPasswordSetEditForm
        return AccountEditForm

    def form_valid(self, form: forms.Form):
        response = super().form_valid(form)
        if 'is_active'in form.changed_data:
            self.object.remove_from_google_workspace_group()
        return response

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if self.request.user.pk == self.object.pk or self.request.user.is_superuser:
            kwargs.update(user=self.object)
        return kwargs


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
                ChangeLog.objects.create(
                    owner_id=self.request.user.pk,
                    instance_type=ContentType.objects.get_for_model(Transaction),
                    instance_id=created_transaction.pk,
                    change_type=ChangeLog.ChangeType.CREATE
                )
                account = created_transaction.account
                if created_transaction.purpose in [
                    Transaction.TransactionPurpose.CLUB_MEMBERSHIP,
                    Transaction.TransactionPurpose.DEBTS
                ] and account.is_late_with_club_membership_payment:
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


class TransactionEdit(LoginRequiredMixin, PermissionsRequiredMixin, UpdateView):
    template_name = 'transaction/edit.html'
    model = Transaction
    form_class = TransactionEditForm
    permissions_required = perms.transaction_edit_perms

    def get_success_url(self):
        return reverse('accounts:detail', args=[self.get_form().instance.account.pk])


class AccountTransactionsEmbeddedView(TemplateView):
    template_name = 'account/embedded.html'

    def get(self, request, *args, **kwargs):
        token = request.GET.get('auth')

        if not token:
            return HttpResponse('Auth token is missing', status=400)

        try:
            payload = jwt.decode(token, settings.API_SECRET, algorithms='HS256')
        except jwt.InvalidTokenError:
            return HttpResponse('Token is invalid', status=401)

        if 'registration_number' not in payload:
            return HttpResponse('Token is invalid', status=401)

        registration_number = payload['registration_number']

        if not registration_number:
            raise Http404()
            
        registration_number = registration_number.replace('MTBO', '')

        self.account = get_object_or_404(Account, registration_number=registration_number)

        return super().get(request, *args, **kwargs)


    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        context_data.update(
            account=self.account
        )
        return context_data


class AccountTransactionsView(TemplateView):
    template_name = 'account/transactions.html'

    def get(self, request, *args, **kwargs):
        self.account = get_object_or_404(Account, key=kwargs['key'])
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)
        context_data.update(
            account=self.account
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

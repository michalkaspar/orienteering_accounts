import typing
import uuid
import logging

from datetime import datetime
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.db.models import Sum, QuerySet
from django.db.models.functions import Coalesce
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _

from orienteering_accounts.core.models import BaseModel
from orienteering_accounts.core.templatetags.core import format_date
from orienteering_accounts.oris import models as oris_models
from orienteering_accounts.oris.client import ORISClient
from orienteering_accounts.core.utils import emails as email_utils
from orienteering_accounts.google.client import client as google_client
from orienteering_accounts.rb.models import Transaction as BankTransactionSchema


logger = logging.getLogger(__name__)


class LazyPermission(object):
    """ Descriptor returns function, that check, if permission is in account's cached permissions """
    def __get__(self, account, objtype=None):
        if not hasattr(account, '_cached_perms') and not account.is_superuser:
            account._cached_perms = {
                x: True
                for x in account.role.permissions.all().values_list('code', flat=True)
            }

        if account.is_superuser:
            return lambda perm: True

        return lambda perm: account._cached_perms.get(perm, False)


class Permission(BaseModel):
    """ Defines what employee can do """
    name = models.CharField(
        max_length=255,
        verbose_name=_('Název')
    )
    code = models.CharField(max_length=256, verbose_name=_('Kód'), db_index=True, unique=True)

    def __str__(self):
        return self.name


class Role(BaseModel):
    """ Defines, what type of employee has what permissions """
    name = models.CharField(max_length=256, verbose_name=_('admin-role-name-label'))
    permissions = models.ManyToManyField(
        'account.Permission',
        related_name='roles',
        blank=True,
        verbose_name=_('Práva')
    )

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('accounts:role:list')


class PaymentPeriod(BaseModel):
    date_from = models.DateField(verbose_name=_('Platnost od'))
    date_to = models.DateField(verbose_name=_('Platnost do'))

    def get_absolute_url(self):
        return reverse('accounts:payment_period:list')

    def __str__(self):
        return f'{format_date(self.date_from)} - {format_date(self.date_to)}'


class AccountManager(BaseUserManager):

    def __init__(self, is_active=True, *args, **kwargs):
        self.is_active = is_active
        super().__init__(*args, **kwargs)

    def get_queryset(self, *args, **kwargs):
        qs = super().get_queryset(*args, **kwargs)
        if self.is_active:
            return qs.filter(is_active=True)
        return qs


class Account(PermissionsMixin, AbstractBaseUser, BaseModel):

    USERNAME_FIELD = EMAIL_FIELD = 'registration_number'

    class Gender(models.TextChoices):
        MAN = oris_models.Gender.MALE.value, _('Muž')
        WOMAN = oris_models.Gender.FEMALE.value, _('Žena')

    registration_number: str = models.CharField(max_length=7, verbose_name=_('Registrační číslo'), unique=True, db_index=True)
    gender: Gender = models.CharField(max_length=5, choices=Gender.choices, verbose_name=_('Pohlaví'))
    licence: str = models.CharField(max_length=5, verbose_name=_('Licence'))
    first_name: str = models.CharField(max_length=50, verbose_name=_('Křestní jméno'))
    last_name: str = models.CharField(max_length=50, verbose_name=_('Příjmení'))
    si: str = models.CharField(max_length=30, verbose_name=_('SI'))
    born_year: int = models.PositiveIntegerField(verbose_name=_('Ročník'))
    is_late_with_club_membership_payment = models.BooleanField(default=False)
    init_balance = models.DecimalField(decimal_places=2, max_digits=9, default=Decimal(0))
    leader_key = models.UUIDField(null=True)
    email = models.EmailField(null=True)
    email2 = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)
    leader_priority = models.PositiveSmallIntegerField(default=0)
    clubroom_chip_number = models.CharField(max_length=255, blank=True, verbose_name=_('Číslo čipu od klubovny'))

    # ORIS fields
    oris_id: int = models.PositiveIntegerField(unique=True)
    oris_paid: int = models.PositiveSmallIntegerField(verbose_name=_('ORIS Paid'))
    oris_club_id: int = models.PositiveIntegerField()  # TODO enum
    oris_club_member_id = models.PositiveIntegerField(null=True)
    oris_fee: int = models.PositiveIntegerField()  # TODO enum

    role = models.ForeignKey(
        'account.Role',
        null=True,
        related_name='accounts',
        on_delete=models.PROTECT,
        verbose_name=_('Role')
    )

    key = models.UUIDField(default=uuid.uuid4)

    ifperm = LazyPermission()
    objects = AccountManager()
    all_objects = AccountManager(is_active=False)

    def __str__(self):
        return self.full_name_inv

    @classmethod
    def upsert_from_oris(cls, registered_user):
        account, created = cls.all_objects.update_or_create(
            registration_number=registered_user.registration_number,
            defaults=registered_user.dict()
        )

        if created:
            club_member = ORISClient.get_club_member(account.oris_id)
            account.email = club_member.email
            account.save(update_fields=['email'])  # We update only email from ORIS club member at the moment

            account.send_account_created_info_email()
            account.add_to_google_workspace_group()

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'

    @property
    def full_name_inv(self):
        return f'{self.last_name} {self.first_name}'

    @property
    def balance(self) -> Decimal:
        return self.init_balance + Decimal(str(
            self.transactions.exclude(
                purpose=Transaction.TransactionPurpose.CLUB_MEMBERSHIP
            ).aggregate(balance=Coalesce(Sum('amount'), Decimal(0)))['balance'])
        )

    @property
    def balance_without_entries(self) -> Decimal:
        return self.init_balance + Decimal(str(
            self.transactions.exclude(
                purpose=Transaction.TransactionPurpose.CLUB_MEMBERSHIP
            ).exclude(
                origin_entry__isnull=False
            ).aggregate(balance=Coalesce(Sum('amount'), Decimal(0)))['balance'])
        )

    @property
    def club_membership_paid(self):
        return self.transactions.filter(purpose=Transaction.TransactionPurpose.CLUB_MEMBERSHIP).exists()

    @property
    def debts_paid(self):
        return self.balance >= Decimal(0)

    def add_entry_rights_in_oris(self):
        ORISClient.set_club_entry_rights(self.oris_club_member_id, can_entry_self=True)

    def remove_entry_rights_in_oris(self):
        ORISClient.set_club_entry_rights(self.oris_club_member_id, can_entry_self=False)

    @classmethod
    def get_accounts_to_remove_entry_rights_in_oris(cls) -> QuerySet['Account']:
        for account in cls.objects.all():
            if not (account.debts_paid and account.club_membership_paid):
                yield account

    def get_transactions_descendant(self):
        return self.transactions.order_by('-created')

    @property
    def debts_payment_qr_url(self):
        return f"https://api.paylibo.com/paylibo/generator/czech/image?accountNumber={settings.CLUB_BANK_ACCOUNT_NUMBER}&bankCode={settings.CLUB_BANK_CODE}&amount={self.debts_payment_amount}&currency=CZK&message={self.debts_payment_message}&size=200&vs={self.debts_variable_symbol}"

    @property
    def debts_payment_message(self):
        return f'OP Mistrovské soutěže {self.full_name}'

    @property
    def debts_variable_symbol(self):
        number = self.registration_number.replace('TZL', '')
        if int(number[:2]) > 92:
            return f'1001{number}'
        return f'1000{number}'

    @property
    def club_membership_payment_message(self):
        return f'OP {self.full_name}'

    @property
    def club_membership_payment_amount(self):
        return Decimal('2000.00').quantize(Decimal(1)) if self.is_adult else Decimal('4000.00').quantize(Decimal(1))

    @property
    def rest_club_membership_payment_amount(self):
        return Decimal('1000.00').quantize(Decimal(1)) if self.is_adult else Decimal('1500.00').quantize(Decimal(1))

    @property
    def debts_payment_amount(self):
        return -self.balance.quantize(Decimal('1'))

    @property
    def club_membership_payment_qr_url(self):
        return f"https://api.paylibo.com/paylibo/generator/czech/image?accountNumber={settings.CLUB_BANK_ACCOUNT_NUMBER}&bankCode={settings.CLUB_BANK_CODE}&amount={self.club_membership_payment_amount}&currency=CZK&message={self.club_membership_payment_message}&size=200"

    @property
    def rest_club_membership_payment_qr_url(self):
        return f"https://api.paylibo.com/paylibo/generator/czech/image?accountNumber={settings.CLUB_BANK_ACCOUNT_NUMBER}&bankCode={settings.CLUB_BANK_CODE}&amount={self.rest_club_membership_payment_amount}&currency=CZK&message={self.club_membership_payment_message}&size=200"

    @property
    def is_adult(self):
        current_year = datetime.now().year
        born_year = self.born_year + 2000 if self.born_year < current_year - 2000 else self.born_year + 1900
        return current_year - born_year > 20

    @property
    def email_recipients(self) -> typing.List[str]:
        if self.email2:
            return [self.email, self.email2]
        return [self.email]

    def send_payment_info_email(self):

        context = {
            'account': self,
            'club_bank_account_number': f'{settings.CLUB_BANK_ACCOUNT_NUMBER}/{settings.CLUB_BANK_CODE}'
        }

        html_content = render_to_string('emails/account_payment_info.html', context)

        email_utils.send_email(
            recipient_list=self.email_recipients,
            subject=f'Platba oddílových příspěvků - {self.full_name } {self.registration_number}',
            html_content=html_content
        )

    def send_rest_payment_info_email(self):

        context = {
            'account': self,
            'club_bank_account_number': f'{settings.CLUB_BANK_ACCOUNT_NUMBER}/{settings.CLUB_BANK_CODE}'
        }

        html_content = render_to_string('emails/account_rest_payment_info.html', context)

        email_utils.send_email(
            recipient_list=self.email_recipients,
            subject=f'Platba oddílových příspěvků druhé pololetí - {self.full_name } {self.registration_number}',
            html_content=html_content
        )

    def send_debts_payment_info_email(self):

        if self.balance >= 0:
            return

        context = {
            'account': self,
            'club_bank_account_number': f'{settings.CLUB_BANK_ACCOUNT_NUMBER}/{settings.CLUB_BANK_CODE}',
            'domain': settings.PROJECT_DOMAIN
        }

        html_content = render_to_string('emails/account_debts_payment_info.html', context)

        email_utils.send_email(
            recipient_list=self.email_recipients,
            subject=f'Platba dluhů jaro 2024 - {self.full_name } {self.registration_number}',
            html_content=html_content
        )

    def send_account_created_info_email(self):
        context = {
            'account': self
        }

        html_content = render_to_string('emails/account_created_info.html', context)

        email_utils.send_email(
            recipient_list=settings.ACCOUNT_CREATED_EMAILS_SEND_TO,
            subject=f'Nový účet v IS - {self.full_name} {self.registration_number}',
            html_content=html_content
        )

    def get_absolute_url(self):
        return reverse('accounts:detail', args=[self.pk])

    def add_to_google_workspace_group(self, group_email: str = settings.GOOGLE_GROUP_MEMBERS):
        google_client.add_member(self.email, group_email=group_email)
        if self.email2:
            google_client.add_member(self.email2, group_email=group_email)

    def remove_from_google_workspace_group(self, group_email: str = settings.GOOGLE_GROUP_MEMBERS, email: str = None, email2: str = None):
        email = email or self.email
        email2 = email2 or self.email2
        google_client.delete_member(email, group_email=group_email)
        if email2:
            google_client.delete_member(email2, group_email=group_email)

    @classmethod
    def process_bank_transaction(cls, bank_transaction: BankTransactionSchema):
        variable_symbol = bank_transaction.variable_symbol
        amount = bank_transaction.amount.value

        if not variable_symbol or amount <= 0:
            return

        if variable_symbol.startswith('1001') or variable_symbol.startswith('1000'):

            registration_number = variable_symbol[4:]

            account = cls.objects.filter(registration_number=f'TZL{registration_number}').first()

            if account:
                account.bank_transactions.get_or_create(
                    remote_id=bank_transaction.entryReference,
                    defaults=dict(
                        date=bank_transaction.valueDate,
                        amount=amount,
                        charged=True,
                        transaction_data=bank_transaction.dict()
                    )
                )

                account.transactions.create(
                    amount=amount,
                    purpose=Transaction.TransactionPurpose.DEBTS
                )
                logger.info('Processed and charged debts bank transactions', extra={'account': account, 'amount': amount})



class Transaction(BaseModel):

    class TransactionPurpose(models.TextChoices):
        CLUB_MEMBERSHIP = 'CLUB_MEMBERSHIP', _('Oddílový příspěvek')
        OTHER = 'JINÉ', _('Jiné')
        DEBTS = 'DLUHY', _('Dluhy')
        ENTRY = 'ENTRY', _('Účast na závodech')
        ENTRY_OTHER = 'ENTRY_OTHER', _('Další náklady na závodech')

    account = models.ForeignKey('account.Account', on_delete=models.CASCADE, related_name='transactions')
    period = models.ForeignKey('account.PaymentPeriod', null=True, blank=True, on_delete=models.SET_NULL, verbose_name=_('Období'))
    amount = models.DecimalField(decimal_places=2, max_digits=9, verbose_name=_('Částka'))
    purpose = models.CharField(max_length=50, choices=TransactionPurpose.choices, default=TransactionPurpose.CLUB_MEMBERSHIP, verbose_name=_('Účel transakce'))
    note = models.TextField(verbose_name=_('Poznámka'), blank=True, default='')
    origin_entry = models.ForeignKey('entry.Entry', on_delete=models.SET_NULL, null=True, related_name='transactions')

    def __str__(self):
        return f'{self.account} {self.get_purpose_display()} {self.amount}'

    def get_absolute_url(self):
        return reverse('accounts:detail', args=[self.account.pk])

    @property
    def is_event(self):
        return self.purpose in [self.TransactionPurpose.ENTRY, self.TransactionPurpose.ENTRY_OTHER]

    @property
    def is_club_membership(self):
        return self.purpose == self.TransactionPurpose.CLUB_MEMBERSHIP


class BankTransaction(BaseModel):
    remote_id = models.CharField(max_length=255, verbose_name=_('ID transakce'), unique=True, db_index=True)
    date = models.DateTimeField(verbose_name=_('Datum'))
    account = models.ForeignKey('account.Account', on_delete=models.CASCADE, related_name='bank_transactions')
    amount = models.DecimalField(decimal_places=2, max_digits=9, verbose_name=_('Částka'))
    charged = models.BooleanField(default=False, verbose_name=_('Zúčtováno'))
    transaction_data = models.JSONField(verbose_name=_('Data transakce'))

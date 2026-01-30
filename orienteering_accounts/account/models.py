import json
import typing
import uuid
import logging
from collections import defaultdict

from datetime import datetime, date, timedelta
from decimal import Decimal

import redis
from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.db.models import Sum, QuerySet, Q
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
from orienteering_accounts.oris.models import UserRanking
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

    @classmethod
    def get_member_role(cls) -> 'Role':
        return cls.objects.get(name='Člen')


class PaymentPeriod(BaseModel):
    date_from = models.DateField(verbose_name=_('Platnost od'))
    date_to = models.DateField(verbose_name=_('Platnost do'))

    class Meta:
        ordering = ('-date_to',)

    def get_absolute_url(self):
        return reverse('accounts:payment_period:list')

    def __str__(self):
        return f'{format_date(self.date_from)} - {format_date(self.date_to)}'

    @classmethod
    def get_last_period(cls) -> 'PaymentPeriod':
        return cls.objects.order_by('-date_to').first()


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
    removed_from_google_workspace = models.BooleanField(default=False)
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

        club_member = ORISClient.get_club_member(account.oris_id)

        if club_member.email != account.email:
            if account.email:
                account.remove_from_google_workspace_group()
            account.email = club_member.email
            account.save(update_fields=['email'])  # We update only email from ORIS club member at the moment
            account.add_to_google_workspace_group()

        if created:
            account.role = Role.get_member_role()
            account.send_account_created_info_email()
            account.save()

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
        today = date.today()
        return self.transactions.filter(
            purpose=Transaction.TransactionPurpose.CLUB_MEMBERSHIP,
            period__date_to__gte=today,
        ).exists()

    @property
    def debts_paid(self):
        return self.balance >= Decimal(0)

    def add_entry_rights_in_oris(self):
        ORISClient.set_club_entry_rights(self.oris_club_member_id, can_entry_self=True)

    def remove_entry_rights_in_oris(self):
        ORISClient.set_club_entry_rights(self.oris_club_member_id, can_entry_self=False)

    @classmethod
    def get_accounts_to_remove_entry_rights_in_oris(cls) -> QuerySet['Account']:
        for account in cls.objects.filter(is_late_with_club_membership_payment=False):
            if not account.club_membership_paid:
                yield account

    @classmethod
    def get_accounts_to_remove_from_google_workspace(cls) -> QuerySet['Account']:
        today = date.today()
        for account in cls.all_objects.filter(removed_from_google_workspace=False):
            if not account.transactions.filter(
                purpose=Transaction.TransactionPurpose.CLUB_MEMBERSHIP,
                period__date_to__gte=today - timedelta(weeks=12),
            ).exists():
                yield account

    def get_transactions_descendant(self, filters: Q = None) -> typing.List['Transaction']:
        qs = self.transactions.order_by('-created')

        if filters:
            qs = qs.filter(filters)

        other_debts_by_origin_entry_id: dict[int, typing.List[Transaction]] = defaultdict(list)

        for other_entry_transaction in qs.filter(
            purpose=Transaction.TransactionPurpose.ENTRY_OTHER,
            origin_entry__isnull=False
        ):
            other_debts_by_origin_entry_id[other_entry_transaction.origin_entry_id].append(other_entry_transaction)

        transactions = []

        for transaction in qs.exclude(purpose=Transaction.TransactionPurpose.ENTRY_OTHER):
            transaction.other_debts = other_debts_by_origin_entry_id.get(transaction.origin_entry_id, [])
            # For ENTRY transactions with linked other debts, precompute total amount (base + others)
            if transaction.purpose == Transaction.TransactionPurpose.ENTRY and transaction.other_debts:
                others_sum = sum((d.amount for d in transaction.other_debts), Decimal('0'))
                transaction.total_with_others = (transaction.amount or Decimal('0')) + others_sum
            transactions.append(transaction)

        return transactions

    def get_transactions_descendant_this_year(self) -> typing.List['Transaction']:
        return self.get_transactions_descendant(
            filters=Q(created__year=datetime.now().year)
        )

    def get_transactions_descendant_other(self) -> typing.List['Transaction']:
        # Return all transactions except those from the current year
        return self.get_transactions_descendant(
            filters=~Q(created__year=datetime.now().year)
        )

    def get_transactions_other_sum(self) -> Decimal:
        """Calculate the sum of all transactions from previous years (excluding current year)"""
        result = self.transactions.filter(
            ~Q(created__year=datetime.now().year)
        ).exclude(
            purpose=Transaction.TransactionPurpose.CLUB_MEMBERSHIP
        ).aggregate(
            total=Coalesce(Sum('amount'), Decimal(0))
        )
        return Decimal(str(self.init_balance + result['total']))

    @property
    def debts_payment_qr_url(self):
        return f"https://api.paylibo.com/paylibo/generator/czech/image?accountNumber={settings.CLUB_BANK_ACCOUNT_NUMBER}&bankCode={settings.CLUB_BANK_CODE}&amount={self.debts_payment_amount}&currency=CZK&message={self.debts_payment_message}&size=200&vs={self.debts_variable_symbol}"

    @property
    def debts_payment_qr_url_no_amount(self):
        """QR code URL for debt payment without amount (keeps variable symbol for automatic matching)"""
        return f"https://api.paylibo.com/paylibo/generator/czech/image?accountNumber={settings.CLUB_BANK_ACCOUNT_NUMBER}&bankCode={settings.CLUB_BANK_CODE}&currency=CZK&message={self.debts_payment_message}&size=200&vs={self.debts_variable_symbol}"

    @property
    def debts_payment_message(self):
        return f'OP Mistrovské soutěže {self.full_name}'

    @property
    def debts_variable_symbol(self):
        number = self.registration_number.replace('TZL', '')
        return f'1000{number}'

    @property
    def club_membership_variable_symbol(self):
        number = self.registration_number.replace('TZL', '')
        return f'{datetime.now().year}{number}'

    @property
    def club_membership_payment_message(self):
        return f'OP {self.full_name}'

    @property
    def club_membership_payment_amount(self):
        return Decimal('2000.00').quantize(Decimal(1)) if self.is_adult else Decimal('5000.00').quantize(Decimal(1))

    @property
    def rest_club_membership_payment_amount(self):
        return Decimal('1000.00').quantize(Decimal(1)) if self.is_adult else Decimal('1500.00').quantize(Decimal(1))

    @property
    def debts_payment_amount(self):
        return -self.balance.quantize(Decimal('1'))

    @property
    def club_membership_payment_qr_url(self):
        return f"https://api.paylibo.com/paylibo/generator/czech/image?accountNumber={settings.CLUB_BANK_ACCOUNT_NUMBER}&bankCode={settings.CLUB_BANK_CODE}&amount={self.club_membership_payment_amount}&currency=CZK&message={self.club_membership_payment_message}&size=200&vs={self.club_membership_variable_symbol}"

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
            subject=f'Upozornění na záporný zůstatek v IS - {self.full_name} {self.registration_number}',
            html_content=html_content
        )

    def send_entry_rights_removed_info_email(self):
        context = {
            'account': self,
            'club_bank_account_number': f'{settings.CLUB_BANK_ACCOUNT_NUMBER}/{settings.CLUB_BANK_CODE}',
            'domain': settings.PROJECT_DOMAIN
        }

        html_content = render_to_string('emails/account_entry_rights_removed_info.html', context)

        email_utils.send_email(
            recipient_list=self.email_recipients,
            subject=f'Odebrání přihlašovacích práv v ORIS - {self.full_name} {self.registration_number}',
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
        self.removed_from_google_workspace = False
        self.save(update_fields=['removed_from_google_workspace'])

    def remove_from_google_workspace_group(self, group_email: str = settings.GOOGLE_GROUP_MEMBERS, email: str = None, email2: str = None):
        email = email or self.email
        email2 = email2 or self.email2
        google_client.delete_member(email, group_email=group_email)
        if email2:
            google_client.delete_member(email2, group_email=group_email)
        self.removed_from_google_workspace = True
        self.save(update_fields=['removed_from_google_workspace'])

    @classmethod
    def process_bank_transaction(cls, bank_transaction: BankTransactionSchema, payment_period: PaymentPeriod):
        variable_symbol = bank_transaction.variable_symbol
        amount = bank_transaction.amount.value

        if not variable_symbol or amount <= 0:
            return

        debts_variable_symbol_prefixes = ('1000', '1001')
        current_year = datetime.now().year
        club_membership_variable_symbol_prefixes = (str(current_year), str(current_year - 1))

        if any(prefix in variable_symbol for prefix in debts_variable_symbol_prefixes + club_membership_variable_symbol_prefixes):

            registration_number = variable_symbol.strip().lstrip('0')[4:]

            account = cls.all_objects.filter(registration_number=f'TZL{registration_number}').first()

            transaction_kwargs = {
                "amount": amount,
                "note": "Importováno z IB.",
                "author_name": "Systém",
            }

            if account:
                if variable_symbol.startswith(club_membership_variable_symbol_prefixes):
                    # Membership payment
                    transaction_kwargs.update(
                        purpose=Transaction.TransactionPurpose.CLUB_MEMBERSHIP,
                        period=payment_period
                    )
                    purpose = BankTransaction.BankTransactionPurpose.CLUB_MEMBERSHIP

                    if not account.is_active:
                        account.is_active = True
                        account.save(update_fields=['is_active'])

                    if account.removed_from_google_workspace:
                        account.removed_from_google_workspace = False
                        account.add_to_google_workspace_group()
                        account.save(update_fields=['remove_from_google_workspace'])

                    logger.info('Processed and charged entry bank transactions', extra={'account': account, 'amount': amount})
                else:
                    transaction_kwargs.update(
                        purpose=Transaction.TransactionPurpose.DEBTS
                    )
                    purpose = BankTransaction.BankTransactionPurpose.DEBTS
                    logger.info('Processed and charged debts bank transactions', extra={'account': account, 'amount': amount})

                # Extract sender name and receiver note from bank transaction
                sender_name = ''
                receiver_note = ''
                try:
                    if bank_transaction.entryDetails.transactionDetails.relatedParties.counterParty:
                        sender_name = bank_transaction.entryDetails.transactionDetails.relatedParties.counterParty.name or ''
                except AttributeError:
                    pass
                
                try:
                    if bank_transaction.entryDetails.transactionDetails.remittanceInformation:
                        remittance = bank_transaction.entryDetails.transactionDetails.remittanceInformation
                        receiver_note = remittance.unstructured or remittance.originatorMessage or ''
                except AttributeError:
                    pass

                bank_transaction_obj, created = account.bank_transactions.get_or_create(
                    remote_id=bank_transaction.entryReference,
                    defaults=dict(
                        date=bank_transaction.valueDate,
                        amount=amount,
                        charged=True,
                        transaction_data=bank_transaction.dict(),
                        purpose=purpose,
                        sender_name=sender_name,
                        receiver_note=receiver_note,
                    )
                )

                if created:
                    transaction_kwargs['origin_bank_transaction'] = bank_transaction_obj
                    account.transactions.create(**transaction_kwargs)

    @property
    def ranking(self) -> typing.Optional[UserRanking]:
        ranking_db_client = redis.StrictRedis.from_url(f"{settings.REDIS_LOCATION}/{settings.REDIS_RANKING_DB_NUMBER}")
        ranking = ranking_db_client.hget(settings.REDIS_CLUB_USER_RANKING_KEY, self.registration_number)
        return UserRanking(**json.loads(ranking)) if ranking else None


class Transaction(BaseModel):

    class TransactionPurpose(models.TextChoices):
        CLUB_MEMBERSHIP = 'CLUB_MEMBERSHIP', _('Oddílový příspěvek')
        OTHER = 'JINÉ', _('Jiné')
        DEBTS = 'DLUHY', _('Kredity')
        ENTRY = 'ENTRY', _('Účast na závodech')
        ENTRY_OTHER = 'ENTRY_OTHER', _('Další náklady na závodech')

    account = models.ForeignKey('account.Account', on_delete=models.CASCADE, related_name='transactions')
    period = models.ForeignKey('account.PaymentPeriod', null=True, blank=True, on_delete=models.SET_NULL, verbose_name=_('Období'))
    amount = models.DecimalField(decimal_places=2, max_digits=9, verbose_name=_('Částka'))
    purpose = models.CharField(max_length=50, choices=TransactionPurpose.choices, default=TransactionPurpose.CLUB_MEMBERSHIP, verbose_name=_('Účel transakce'))
    note = models.TextField(verbose_name=_('Poznámka'), blank=True, default='')
    origin_entry = models.ForeignKey('entry.Entry', on_delete=models.SET_NULL, null=True, related_name='transactions')
    origin_bank_transaction = models.ForeignKey('account.BankTransaction', on_delete=models.SET_NULL, null=True, related_name='transactions')
    author_name = models.CharField(max_length=255, verbose_name=_('Autor změny'), blank=True, default='')
    is_future = models.BooleanField(default=False, verbose_name=_('Budoucí transakce'))

    def __str__(self):
        return f'{self.account} {self.get_purpose_display()} {self.amount}'

    def get_absolute_url(self):
        return reverse('accounts:detail', args=[self.account.pk])

    @property
    def is_event(self):
        return self.purpose in [self.TransactionPurpose.ENTRY, self.TransactionPurpose.ENTRY_OTHER]

    @property
    def is_entry(self) -> bool:
        return self.purpose == self.TransactionPurpose.ENTRY

    @property
    def is_club_membership(self):
        return self.purpose == self.TransactionPurpose.CLUB_MEMBERSHIP
    
    @property
    def is_bank_transaction(self) -> bool:
        return self.origin_bank_transaction is not None


class BankTransaction(BaseModel):

    class BankTransactionPurpose(models.TextChoices):
        CLUB_MEMBERSHIP = 'CLUB_MEMBERSHIP', _('Oddílový příspěvek')
        DEBTS = 'DEBTS', _('Dluhy')

    remote_id = models.CharField(max_length=255, verbose_name=_('ID transakce'), unique=True, db_index=True)
    date = models.DateTimeField(verbose_name=_('Datum'))
    account = models.ForeignKey('account.Account', on_delete=models.CASCADE, related_name='bank_transactions')
    amount = models.DecimalField(decimal_places=2, max_digits=9, verbose_name=_('Částka'))
    charged = models.BooleanField(default=False, verbose_name=_('Zúčtováno'))
    transaction_data = models.JSONField(verbose_name=_('Data transakce'))
    purpose = models.CharField(max_length=50, choices=BankTransactionPurpose.choices, default=BankTransactionPurpose.DEBTS, verbose_name=_('Účel transakce'))
    sender_name = models.CharField(max_length=255, verbose_name=_('Jméno odesílatele'), blank=True, default='')
    receiver_note = models.TextField(verbose_name=_('Poznámka pro příjemce'), blank=True, default='')

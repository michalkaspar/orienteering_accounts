from datetime import datetime
from decimal import Decimal

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.db.models import Sum, QuerySet
from django.db.models.functions import Coalesce
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _

from orienteering_accounts.core.models import BaseModel
from orienteering_accounts.core.templatetags.core import format_date
from orienteering_accounts.oris import models as oris_models
from orienteering_accounts.oris.client import ORISClient


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

    # ORIS fields
    oris_id: int = models.PositiveIntegerField(unique=True)
    oris_paid: int = models.PositiveSmallIntegerField(verbose_name=_('ORIS Paid'))
    oris_club_id: int = models.PositiveIntegerField()  # TODO enum
    oris_fee: int = models.PositiveIntegerField()  # TODO enum

    role = models.ForeignKey(
        'account.Role',
        null=True,
        related_name='accounts',
        on_delete=models.PROTECT,
        verbose_name=_('Role')
    )

    ifperm = LazyPermission()
    objects = BaseUserManager()

    def __str__(self):
        return self.full_name

    @classmethod
    def upsert_from_oris(cls, registered_user):
        cls.objects.update_or_create(
            registration_number=registered_user.registration_number,
            defaults=registered_user.dict()
        )

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'

    @property
    def balance(self) -> Decimal:
        return Decimal(str(self.transactions.aggregate(balance=Coalesce(Sum('amount'), 0))['balance']))

    @property
    def club_membership_paid(self):
        return self.transactions.filter(purpose=Transaction.TransactionPurpose.CLUB_MEMBERSHIP).exists()

    @property
    def debts_paid(self):
        return self.transactions.filter(purpose=Transaction.TransactionPurpose.DEBTS).exists()

    def add_entry_rights_in_oris(self):
        ORISClient.set_club_entry_rights(self.oris_id, can_entry_self=True)

    def remove_entry_rights_in_oris(self):
        ORISClient.set_club_entry_rights(self.oris_id, can_entry_self=False)

    @classmethod
    def get_accounts_without_paid_club_membership(cls, deadline: datetime) -> QuerySet['Account']:
        paid_accounts_ids = cls.objects.filter(
            transactions__purpose=Transaction.TransactionPurpose.CLUB_MEMBERSHIP,
            transactions__created__lte=deadline,
            transactions__created__year=deadline.year
        ).values_list('pk', flat=True).distinct()

        return cls.objects.exclude(id__in=paid_accounts_ids)

    def get_transactions_descendant(self):
        return self.transactions.order_by('-created')


class Transaction(BaseModel):

    class TransactionPurpose(models.TextChoices):
        CLUB_MEMBERSHIP = 'CLUB_MEMBERSHIP', _('Oddílový příspěvek')
        OTHER = 'JINÉ', _('Jiné')
        DEBTS = 'DLUHY', _('Dluhy')

    account = models.ForeignKey('account.Account', on_delete=models.CASCADE, related_name='transactions')
    period = models.ForeignKey('account.PaymentPeriod', null=True, blank=True, on_delete=models.SET_NULL, verbose_name=_('Období'))
    amount = models.DecimalField(decimal_places=2, max_digits=9, verbose_name=_('Částka'))
    purpose = models.CharField(max_length=50, choices=TransactionPurpose.choices, default=TransactionPurpose.CLUB_MEMBERSHIP, verbose_name=_('Účel transakce'))
    note = models.TextField(verbose_name=_('Poznámka'), blank=True, default='')

    def __str__(self):
        return f'{self.account} {self.get_purpose_display()} {self.amount}'

    def get_absolute_url(self):
        return reverse('accounts:detail', args=[self.account.pk])

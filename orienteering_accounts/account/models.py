from django.db import models
from django.utils.translation import ugettext_lazy as _

from orienteering_accounts.oris import models as oris_models


class Account(models.Model):

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

    # ORIS fields
    oris_id: int = models.PositiveIntegerField(unique=True)
    oris_paid: int = models.PositiveSmallIntegerField(verbose_name=_('ORIS Paid'))
    oris_club_id: int = models.PositiveIntegerField()  # TODO enum
    oris_fee: int = models.PositiveIntegerField()  # TODO enum

    @classmethod
    def upsert_from_oris(cls, registered_user):
        cls.objects.update_or_create(
            registration_number=registered_user.registration_number,
            defaults=registered_user.dict()
        )


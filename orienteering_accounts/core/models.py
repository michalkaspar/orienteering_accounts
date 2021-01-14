from django.db import models
from django.utils.translation import ugettext_lazy as _


class BaseModel(models.Model):
    KEEP_ORIGINAL_VALUES = False

    created = models.DateTimeField(
        auto_now_add=True,
        editable=False,
        db_index=True,
        verbose_name=_('Datum a čas vzniku'),
    )
    modified = models.DateTimeField(
        auto_now=True,
        editable=False,
        db_index=True,
        verbose_name=_('Datum a čas poslední úpravy'),
    )

    class Meta:
        abstract = True


class Settings(models.Model):
    club_membership_deadline = models.DateTimeField(verbose_name=_('Deadline pro platbu oddílových příspěvků'))

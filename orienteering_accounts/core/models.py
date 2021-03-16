from django.contrib.contenttypes.fields import GenericForeignKey
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


class ChangeLog(BaseModel):

    class ChangeType(models.TextChoices):
        CREATE = 'CREATE', _('Vytvořil')
        UPDATE = 'UPDATE', _('Změnil')
        DELETE = 'DELETE', _('Smazal')

    owner = models.ForeignKey('account.Account', on_delete=models.CASCADE, related_name='change_logs')
    instance_id = models.PositiveIntegerField()
    instance_type = models.ForeignKey('contenttypes.ContentType', on_delete=models.CASCADE)
    instance = GenericForeignKey('instance_type', 'instance_id')
    change_type = models.CharField(max_length=255, choices=ChangeType.choices, default=ChangeType.UPDATE)

    def __str__(self):
        return f'<a href="{self.instance.get_absolute_url()}">{self.instance}</a>'

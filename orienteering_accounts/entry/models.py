from django.db import models


class Entry(models.Model):
    oris_id = models.PositiveIntegerField(unique=True)
    oris_category_id = models.PositiveIntegerField()
    account = models.ForeignKey('account.Account', related_name='entries', on_delete=models.CASCADE)
    event = models.ForeignKey('event.Event', related_name='entries', on_delete=models.CASCADE)
    fee = models.PositiveIntegerField()
    oris_created = models.DateTimeField(null=True, blank=True)
    oris_updated = models.DateTimeField(null=True, blank=True)
    rent_si: models.BooleanField(default=False)

    @classmethod
    def upsert_from_oris(cls, entry):
        cls.objects.update_or_create(
            account__oris_id=entry.oris_user_id,
            event__oris_id=entry.oris_evet_id,
            defaults=entry.dict()
        )

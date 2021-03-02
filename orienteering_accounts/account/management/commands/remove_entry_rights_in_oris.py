import logging

from django.core.management import BaseCommand
from django.utils import timezone

from orienteering_accounts.account.models import Account
from orienteering_accounts.core.models import Settings

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Removes entry right in ORIS for accounts without membership payment after system deadline'

    def handle(self, **options):
        logger.info(f'Removing entry rights started')

        system_settings = Settings.objects.first()

        for account in Account.get_accounts_without_paid_club_membership(system_settings.club_membership_deadline):
            account.remove_entry_rights_in_oris()
            account.is_late_with_club_membership_payment = True
            account.save(update_fields=['is_late_with_club_membership_payment'])

        logger.info(f'Removing entry rights finished')

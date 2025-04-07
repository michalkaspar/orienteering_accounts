import logging

from django.conf import settings
from django.core.management import BaseCommand
from django.template.loader import render_to_string

from orienteering_accounts.account.models import Account
from orienteering_accounts.core.utils import emails as email_utils

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Removes entry right in ORIS for accounts without membership payment after system deadline'

    def handle(self, **options):
        logger.info(f'Removing entry rights started')

        accounts_disabled = []

        for account in Account.get_accounts_to_remove_entry_rights_in_oris():
            account.remove_entry_rights_in_oris()
            account.is_late_with_club_membership_payment = True
            account.save(update_fields=['is_late_with_club_membership_payment'])

            accounts_disabled.append(account)

            logger.info(f'Removing entry rights for {account}')

        if accounts_disabled:
            context = {
                'accounts': accounts_disabled,
            }

            html_content = render_to_string('emails/removed_entry_rights.html', context)

            email_utils.send_email(
                recipient_list=settings.ACCOUNT_CREATED_EMAILS_SEND_TO,
                subject=f'Byly odebrány startovní práva v ORISu',
                html_content=html_content
            )

        logger.info(f'Removing entry rights finished')

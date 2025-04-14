import logging

from django.conf import settings
from django.core.management import BaseCommand
from django.template.loader import render_to_string

from orienteering_accounts.account.models import Account
from orienteering_accounts.core.utils import emails as email_utils

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Removes accounts from Google workspace for accounts with expired membership payment for more than 3 months'

    def handle(self, **options):
        logger.info(f'Removing accounts from Google workspace started')

        accounts_removed = []

        for account in Account.get_accounts_to_remove_from_google_workspace():
            account.remove_from_google_workspace_group()

            accounts_removed.append(account)

            logger.info(f'Removing {account} from Google workspace')

        if accounts_removed:
            context = {
                'accounts': accounts_removed,
            }

            html_content = render_to_string('emails/removed_from_googlespace.html', context)

            email_utils.send_email(
                recipient_list=settings.ACCOUNT_CREATED_EMAILS_SEND_TO,
                subject=f'Byly odebrány účty z Google workspace',
                html_content=html_content
            )

        logger.info(f'Removing accounts from Google workspace finished')

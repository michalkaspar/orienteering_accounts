import logging

from django.core.management import BaseCommand

from orienteering_accounts.account.models import Account
from orienteering_accounts.oris.client import ORISClient

logger = logging.getLogger(__name__)


class Command(BaseCommand):

    def handle(self, **options):
        logger.info(f'Import of registered users from ORIS started')

        registered_users = ORISClient.get_registered_users()

        for registered_user in registered_users:
            Account.upsert_from_oris(registered_user)

        logger.info(f'Import of registered users from ORIS finished')

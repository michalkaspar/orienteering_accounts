import logging

from django.core.management import BaseCommand

from orienteering_accounts.account.models import Account
from orienteering_accounts.oris.client import ORISClient
from orienteering_accounts.oris import choices as oris_choices

logger = logging.getLogger(__name__)


class Command(BaseCommand):

    def handle(self, **options):
        logger.info(f'Import of registered users from ORIS started')

        registered_ob_users = ORISClient.get_registered_users(sport=oris_choices.SPORT_OB)
        registered_mtbo_users = ORISClient.get_registered_users(sport=oris_choices.SPORT_MTBO)

        for registered_user in registered_ob_users + registered_mtbo_users:
            Account.upsert_from_oris(registered_user)

        logger.info(f'Import of registered users from ORIS finished')

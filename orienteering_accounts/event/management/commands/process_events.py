import logging

from django.core.management import BaseCommand

from orienteering_accounts.event.models import Event
from orienteering_accounts.oris.client import ORISClient

logger = logging.getLogger(__name__)


class Command(BaseCommand):

    def handle(self, **options):
        try:
            logger.info('Started importing events from ORIS')

            Event.import_from_oris()

            logger.info('Finished importing events from ORIS')

            logger.info('Started sending payment info emails')

            Event.send_payment_info_emails()

            logger.info('Finished sending payment info emails')

            logger.info('Started sending entries leader info emails')

            Event.send_leader_entries_emails()

            logger.info('Finished sending entries leader info emails')

            logger.info('Started sending debts leader info emails')

            Event.send_leader_debts_emails()

            logger.info('Finished sending debts leader info emails')
        finally:
            ORISClient.log_request_stats()

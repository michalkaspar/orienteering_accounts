import logging

from django.core.management import BaseCommand

from orienteering_accounts.event.models import Event

logger = logging.getLogger(__name__)


class Command(BaseCommand):

    def handle(self, **options):

        logger.info('Started importing events from ORIS')

        Event.import_from_oris()

        logger.info('Finished importing events from ORIS')

        logger.info('Started refreshing events from ORIS')

        Event.refresh_from_oris()

        logger.info('Finished refreshing events from ORIS')

        logger.info('Started sending payment info emails')

        Event.send_payment_info_emails()

        logger.info('Finished sending payment info emails')

        #  TODO leader email, debts email

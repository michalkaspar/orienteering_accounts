import logging

from django.core.management import BaseCommand

from orienteering_accounts.event.models import Event

logger = logging.getLogger(__name__)


class Command(BaseCommand):

    def handle(self, **options):
        logger.info(f'Send emails about event payment info')

        for event in Event.to_send_payment_info_email():
            logger.info(f'Sending email about event payment info to event {event}')
            event.send_payment_info_email()

        logger.info(f'Send emails about event payment info finished')

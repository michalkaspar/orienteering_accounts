import logging

from django.core.management import BaseCommand

from orienteering_accounts.event.models import Event
from orienteering_accounts.oris.client import ORISClient

logger = logging.getLogger(__name__)


class Command(BaseCommand):

    def handle(self, **options):
        logger.info(f'Import of events from ORIS started')

        events = ORISClient.get_events()

        for event in events:
            Event.upsert_from_oris(event)

        logger.info(f'Import of events from ORIS finished')

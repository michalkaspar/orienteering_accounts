import logging

from django.core.management import BaseCommand

from orienteering_accounts.event.models import Event
from orienteering_accounts.oris.client import ORISClient

logger = logging.getLogger(__name__)


class Command(BaseCommand):

    def handle(self, **options):
        logger.info(f'Refresh events from ORIS started')

        for event in Event.to_refresh():
            oris_event = ORISClient.get_event(event.oris_id)
            event.upsert_from_oris(oris_event)
            event.update_entries()

        logger.info(f'Refresh events from ORIS finished')


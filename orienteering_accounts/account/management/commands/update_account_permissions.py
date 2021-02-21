import logging
import re

from django.core.management import BaseCommand

from orienteering_accounts.account import choices
from orienteering_accounts.account.models import Permission

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Adds missing permissions defined im account choices to database'

    def add_arguments(self, parser):
        parser.add_argument('--remove-unknown', action='store_true', dest='remove_unknown',
                            help='Removes permissions not listed in choices')
        parser.add_argument('--clean', action='store_true', dest='clean', help='Removes existing permissions first')

    def _remove_unexisting(self):
        perm_codes = []
        for perm_code in choices.PERMS_LIST:
            perm_codes.append(perm_code)

        deleted_count, _ = Permission.objects.exclude(code__in=perm_codes).delete()
        logger.info('Removed {} unknown permissions'.format(deleted_count))

    def handle(self, *args, **options):
        if options.get('clean', False):
            Permission.objects.all().delete()
            logger.info('Removed existing permissions')
        elif options.get('remove_unknown', False):
            self._remove_unexisting()

        regex = re.compile('_')
        created_count = 0

        for perm_code in choices.PERMS_LIST:
            perm_name = regex.sub(' ', perm_code)
            _, created = Permission.objects.get_or_create(
                code=perm_code,
                defaults={
                    'name': perm_name,
                }
            )

            if created:
                created_count += 1

        logger.info('Added {} new permissions'.format(created_count))

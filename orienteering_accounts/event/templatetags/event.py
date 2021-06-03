from django import template
from django.conf import settings

register = template.Library()

from orienteering_accounts.event.models import Event


@register.simple_tag
def get_bulletin_url(event: Event):
    if not event.links:
        return None
    for _, link_dict in event.links.items():
        source_type = link_dict.get('SourceType')
        if source_type and source_type.get('ID') == settings.ORIS_SOURCE_TYPE_BULLETIN_ID:
            return link_dict.get('Url')
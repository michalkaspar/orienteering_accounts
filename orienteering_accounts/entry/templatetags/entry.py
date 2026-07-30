from datetime import datetime
from decimal import Decimal

from django import template

from orienteering_accounts.entry.models import Entry

register = template.Library()


@register.simple_tag
def entry_additional_service_value(entry: Entry, additional_service: dict):
    aggregated = Entry.aggregate_additional_services_by_id(entry.additional_services)
    service = aggregated.get(additional_service['ID'])
    if service is None:
        return '-'
    return service['total_fee']

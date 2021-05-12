from datetime import datetime
from decimal import Decimal

from django import template

from orienteering_accounts.entry.models import Entry

register = template.Library()


@register.simple_tag
def entry_additional_service_value(entry: Entry, additional_service: dict):
    for entry_additional_service in entry.additional_services.items():
        if entry_additional_service['Service']['ID'] == additional_service['ID']:
            return entry_additional_service['TotalFee']
    return '-'

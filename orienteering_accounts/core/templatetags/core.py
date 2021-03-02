from datetime import datetime, date

import pytz
from django import template
from django.conf import settings

register = template.Library()


@register.filter
def format_datetime(value):
    if not value:
        return '-'

    if isinstance(value, datetime):
        value = value.astimezone(pytz.timezone(settings.TIME_ZONE))
        return datetime.strftime(value, settings.TEMPLATE_DATETIME_FORMAT)
    if isinstance(value, date):
        return date.strftime(value, settings.TEMPLATE_DATETIME_FORMAT)

    return value


@register.filter
def format_date(value):
    if not value:
        return '-'

    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return date.strftime(value, settings.TEMPLATE_DATE_FORMAT)

    return value
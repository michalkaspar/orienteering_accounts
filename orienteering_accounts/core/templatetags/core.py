from datetime import datetime, date

import pytz
from django import template
from django.conf import settings
from django.http import HttpRequest

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


@register.inclusion_tag("base/templatetags/sortable_th.html")
def sortable_th(request: HttpRequest, order_by: str, label: str):

    ordering = request.GET.get('o')
    desc = False

    if ordering and '-' in ordering:
        ordering = ordering[1:]
        desc = True

    is_active = ordering == order_by

    url = request.get_full_path()

    if is_active:

        if desc:
            url = url.replace(f'o=-{order_by}', f'o={order_by}')
        else:
            url = url.replace(f'o={order_by}', f'o=-{order_by}')

    else:
        if '?' in url:
            url += f'&o={order_by}'
        else:
            url += f'?o={order_by}'

    return {
        'url': url,
        'is_active': is_active,
        'desc': desc,
        'label': label
    }

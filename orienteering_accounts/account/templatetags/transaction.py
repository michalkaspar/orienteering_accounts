from decimal import Decimal

from django import template

register = template.Library()


@register.inclusion_tag('transaction/templatetags/amount.html')
def transaction_amount(amount: Decimal):
    return {'amount': amount}

import logging
from decimal import Decimal

import requests

logger = logging.getLogger(__name__)


def get_exchange_rate_to_czk(currency: str) -> Decimal:
    if not currency or currency == 'CZK':
        return Decimal('1')

    response = requests.get(
        'https://api.coinbase.com/v2/exchange-rates',
        params={'currency': currency}
    )
    response.raise_for_status()

    data = response.json()
    czk_rate = data['data']['rates'].get('CZK')

    if czk_rate is None:
        raise ValueError(f'CZK rate not found for currency {currency}')

    return Decimal(czk_rate)

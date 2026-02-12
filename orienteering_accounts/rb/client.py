import logging
import time
import typing
from datetime import datetime

import requests_pkcs12
from requests.exceptions import HTTPError

from uuid import uuid4
from django.conf import settings

from orienteering_accounts.rb.models import Transaction

logger = logging.getLogger(__name__)

# Retry configuration for transient 5xx server errors
RB_API_MAX_RETRIES = 3
RB_API_RETRY_BACKOFF_BASE = 2  # seconds


class RBBankAPIClient:

    @classmethod
    def make_request(cls, method: str, endpoint: str, params: dict = None, data: dict = None, **kwargs):
        headers = {
            'X-IBM-Client-Id': settings.RB_API_CLIENT_ID,
            'X-Request-Id': str(uuid4()),
            'content-type': 'application/json'
        }

        url = f'{settings.RB_API_URL}/{endpoint}'

        request_func = getattr(requests_pkcs12, method.lower())

        for attempt in range(RB_API_MAX_RETRIES):
            try:
                response = request_func(
                    url,
                    params=params,
                    headers=headers,
                    json=data,
                    pkcs12_filename=settings.RB_API_P12_CERT_PATH,
                    pkcs12_password=settings.RB_API_P12_CERT_PASSWORD,
                    **kwargs
                )
                response.raise_for_status()

                if response.status_code == 204:
                    return None

                return response.json()

            except HTTPError as e:
                # Only retry on 5xx server errors (transient)
                if e.response is not None and 500 <= e.response.status_code < 600:
                    if attempt < RB_API_MAX_RETRIES - 1:
                        wait_time = RB_API_RETRY_BACKOFF_BASE ** (attempt + 1)
                        logger.warning(
                            'RB API returned %s for %s, retrying in %ds (attempt %d/%d)',
                            e.response.status_code, endpoint, wait_time, attempt + 1, RB_API_MAX_RETRIES
                        )
                        time.sleep(wait_time)
                    else:
                        logger.error(
                            'RB API failed after %d retries: %s %s',
                            RB_API_MAX_RETRIES, e.response.status_code, e.response.url
                        )
                        raise
                else:
                    raise

    @classmethod
    def make_get_request(cls, endpoint, params: dict = None, **kwargs):
        return cls.make_request('GET', endpoint, params=params, **kwargs)

    @classmethod
    def make_put_request(cls, endpoint, data: dict = None, **kwargs):
        return cls.make_request('PUT', endpoint, data=data, **kwargs)

    @classmethod
    def make_post_request(cls, endpoint, data: dict = None, **kwargs):
        return cls.make_request('POST', endpoint, data=data, **kwargs)

    @classmethod
    def get_transactions(cls,
                         from_date: datetime,
                         to_date: datetime,
                         bank_account_number: str = settings.CLUB_BANK_ACCOUNT_NUMBER,
                         currency: str = 'CZK',
                         page: int = 1,
                         ) -> typing.List[Transaction]:
        params = {
            'from': from_date.isoformat(),
            'to': to_date.isoformat(),
            'page': page
        }
        endpoint = f'accounts/{bank_account_number}/{currency}/transactions'
        response: dict = cls.make_get_request(endpoint, params=params)

        transactions = []

        if not response:
            return transactions

        for transaction_data in response['transactions']:
            transaction = Transaction(**transaction_data)
            transactions.append(transaction)

        if not response['lastPage']:
            transactions += cls.get_transactions(
                from_date=from_date,
                to_date=to_date,
                bank_account_number=bank_account_number,
                currency=currency,
                page=page + 1
            )

        return transactions

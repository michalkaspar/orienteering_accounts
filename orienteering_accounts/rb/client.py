import typing
from datetime import datetime

import requests_pkcs12

from uuid import uuid4
from django.conf import settings

from orienteering_accounts.rb.models import Transaction


class RBBankAPIClient:

    @classmethod
    def make_request(cls, method: str, endpoint: str, params: dict = None, data: dict = None, **kwargs):
        headers= {
            'X-IBM-Client-Id': settings.RB_API_CLIENT_ID,
            'X-Request-Id': str(uuid4()),
            'content-type': 'application/json'
        }

        url = f'{settings.RB_API_URL}/{endpoint}'

        request_func = getattr(requests_pkcs12, method.lower())

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

        return response.json()

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

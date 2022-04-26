from collections import defaultdict
from decimal import Decimal

import requests
import typing
import logging

from django.conf import settings
from datetime import date

from pydantic import ValidationError

from orienteering_accounts.oris import choices as oris_choices
from orienteering_accounts.oris.models import RegisteredUser, Event, Entry, EventBalance, Result

logger = logging.getLogger(__name__)


class ORISClient:

    @classmethod
    def make_request(cls, method: str, endpoint: str, params: dict = None, data: dict = None, **kwargs):
        default_params = {
            'format': 'json',
            'method': endpoint
        }

        if params:
            default_params.update(**params)

        params = default_params
        request_func = getattr(requests, method.lower())

        response = request_func(settings.ORIS_API_URL, params=params, json=data, **kwargs)
        response.raise_for_status()

        if not response:
            return None

        response_data = response.json()

        return response_data['Data']

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
    def get_registered_users(cls, year: int = None, sport: int = oris_choices.SPORT_OB, club_id: int = settings.CLUB_ID) -> typing.List[RegisteredUser]:
        params = {
            'year': year or date.year,
            'sport': sport
        }
        response_data = cls.make_get_request('getRegistration', params=params)

        registered_users = []

        for reg_id, registered_user_dict in response_data.items():

            if registered_user_dict.get('ClubID') == club_id:
                registered_users.append(RegisteredUser(**registered_user_dict))

        return registered_users

    @classmethod
    def get_events(cls, sport: int = oris_choices.SPORT_OB, include_unofficial_events=0) -> typing.List[Event]:
        params = {
            'sport': sport,
            'all': include_unofficial_events
        }
        response_data = cls.make_get_request('getEventList', params=params)

        events = []

        if response_data:
            for reg_id, event_dict in response_data.items():
                try:
                    events.append(Event(**event_dict))
                except ValidationError:
                    logger.error('Invalid ORIS event, skipping', exc_info=True)
        return events

    @classmethod
    def get_event(cls, event_id: int) -> Event:
        params = {
            'id': event_id
        }
        response_data = cls.make_get_request('getEvent', params=params)

        return Event(**response_data)

    @classmethod
    def get_event_entries(cls, event_id: int, club_id: int = settings.CLUB_ID):
        params = {
            'eventid': event_id,
            'clubid': club_id,
            'username': settings.ORIS_API_USERNAME,
            'password': settings.ORIS_API_PASSWORD
        }
        response_data = cls.make_get_request('getEventEntries', params=params)

        entries = []

        if response_data:
            for entry_id, entry_dict in response_data.items():
                if entry_dict.get('UserID'):
                    entries.append(Entry(**entry_dict))

        return entries

    @classmethod
    def get_event_results(cls, event_id: int, club_id: int = settings.CLUB_ID) -> typing.Dict[str, Result]:
        params = {
            'eventid': event_id,
            'clubid': club_id
        }
        response_data = cls.make_get_request('getEventResults', params=params)

        results = {}
        if response_data:
            for result_id, result_dict in response_data.items():
                result = Result(**result_dict)
                results[result.registration_number] = result

        return results

    @classmethod
    def get_event_additional_services(cls, event_id: int, club_id: int = settings.CLUB_ID) -> typing.Dict[int, typing.List]:
        params = {
            'eventid': event_id,
            'clubid': club_id
        }
        response_data = cls.make_get_request('getEventServiceEntries', params=params)

        additional_services = defaultdict(list)

        if response_data:
            for _, service_dict in response_data.items():
                additional_services[int(service_dict['UserID'])].append(service_dict)

        return additional_services

    @classmethod
    def set_club_entry_rights(cls, user_id: int, club_key: int = settings.CLUB_KEY, can_entry_self: bool = None, can_entry_others: bool = None):
        params = {
            'clubuser': user_id,
            'clubkey': club_key
        }

        if can_entry_self is not None:
            params.update(self=int(can_entry_self), other=0)
        #if can_entry_others is not None:
        #    params.update(other=can_entry_others)

        return cls.make_get_request('setClubEntryRights', params=params)

    @classmethod
    def get_club_event_balance(cls, event_id: int, club_id: int = settings.CLUB_ID) -> typing.Optional[EventBalance]:
        params = {
            'eventid': event_id
        }
        response_data = cls.make_get_request('getEventBalance', params=params)

        if response_data:
            for _, club_dict in response_data['Clubs'].items():
                if club_dict['ClubID'] == club_id:
                    return EventBalance(**club_dict)

        return None

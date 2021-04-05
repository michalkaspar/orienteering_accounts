from decimal import Decimal

import requests
import typing

from django.conf import settings
from datetime import date

from orienteering_accounts.oris import choices as oris_choices
from orienteering_accounts.oris.models import RegisteredUser, Event, Entry


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

        for reg_id, event_dict in response_data.items():
            events.append(Event(**event_dict))

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
            'clubid': club_id
        }
        response_data = cls.make_get_request('getEventEntries', params=params)

        entries = []

        if response_data:
            for entry_id, entry_dict in response_data.items():
                entries.append(Entry(**entry_dict))

        return entries

    @classmethod
    def set_club_entry_rights(cls, user_id: int, club_key: int = settings.CLUB_KEY, can_entry_self: bool = None, can_entry_others: bool = None):
        params = {
            'clubuser': user_id,
            'clubkey': club_key
        }

        if can_entry_self:
            params.update(self=can_entry_self)
        if can_entry_others:
            params.update(other=can_entry_others)

        return cls.make_post_request('setClubEntryRights', params=params)

    @classmethod
    def get_club_event_balance(cls, event_id: int, club_id: int = settings.CLUB_ID) -> typing.Optional[Decimal]:
        params = {
            'eventid': event_id
        }
        response_data = cls.make_get_request('getEventBalance', params=params)

        if response_data:
            for _, club_dict in response_data['Clubs'].items():
                if club_dict['ClubID'] == club_id:
                    return Decimal(club_dict['ToBePaid'])

        return None

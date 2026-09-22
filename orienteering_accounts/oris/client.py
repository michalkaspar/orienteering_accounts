import csv
import time
from collections import defaultdict
from enum import Enum
from io import StringIO

import requests
import typing
import logging

from django.conf import settings
from django.core.cache import cache
from datetime import date, datetime

from pydantic import ValidationError

from orienteering_accounts.oris import choices as oris_choices
from orienteering_accounts.oris.models import RegisteredUser, Event, Entry, EventBalance, Result, LegEntry, BaseEntry, \
    ClubMember, UserRanking, Gender, Club, ClubHosting

logger = logging.getLogger(__name__)

TOO_MANY_REQUESTS = 429

# ORIS throttles clients that fire too many requests in a row, retry such requests instead of failing
ORIS_API_MAX_ATTEMPTS = 5
ORIS_API_RETRY_BACKOFF_SECONDS = 2
ORIS_API_RETRY_MAX_DELAY_SECONDS = 60


class ORISClient:

    @classmethod
    def _retry_delay(cls, response, attempt: int) -> float:
        retry_after = response.headers.get('Retry-After')

        if retry_after:
            try:
                return min(max(float(retry_after), 0), ORIS_API_RETRY_MAX_DELAY_SECONDS)
            except ValueError:
                pass

        return min(ORIS_API_RETRY_BACKOFF_SECONDS * 2 ** (attempt - 1), ORIS_API_RETRY_MAX_DELAY_SECONDS)

    @classmethod
    def request_with_retry(cls, request_func, *args, **kwargs):
        for attempt in range(1, ORIS_API_MAX_ATTEMPTS + 1):
            response = request_func(*args, **kwargs)

            if response.status_code != TOO_MANY_REQUESTS or attempt == ORIS_API_MAX_ATTEMPTS:
                return response

            delay = cls._retry_delay(response, attempt)
            logger.warning(
                f'ORIS API throttled the request, retrying in {delay} s '
                f'(attempt {attempt} of {ORIS_API_MAX_ATTEMPTS}).'
            )
            time.sleep(delay)

        return response

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

        response = cls.request_with_retry(request_func, settings.ORIS_API_URL, params=params, json=data, **kwargs)
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
    def get_registered_users(cls,
                             year: int = None,
                             sport: int = oris_choices.SPORT_OB,
                             club_id: typing.Optional[int] = None,
                             licence: typing.Optional[str] = None,
                             ) -> typing.List[RegisteredUser]:
        year = year or datetime.now().year
        cache_key = settings.ORIS_REGISTRATIONS_CACHE_KEY_PATTERN.format(sport=sport, year=year)
        response_data = cache.get(cache_key)

        if response_data is None:
            response_data = cls.make_get_request('getRegistration', params={'year': year, 'sport': sport})

            if response_data:
                cache.set(cache_key, response_data, settings.ORIS_REGISTRATIONS_CACHE_TIMEOUT)

        registered_users = []

        if not response_data:
            return registered_users

        for reg_id, registered_user_dict in response_data.items():

            if licence and registered_user_dict.get('Lic') != licence:
                continue

            if club_id and registered_user_dict.get('ClubID') != club_id:
                continue

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
                    logger.warning('Invalid ORIS event, skipping', exc_info=True)
        return events

    @classmethod
    def get_event(cls, event_id: int) -> Event:
        params = {
            'id': event_id
        }
        response_data = cls.make_get_request('getEvent', params=params)

        return Event(**response_data)

    @classmethod
    def get_event_entries(cls, event_id: int, club_id: int = settings.CLUB_ID) -> typing.List[BaseEntry]:
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
                elif entry_dict.get('Legs'):
                    for leg_id, leg_dict in entry_dict.get('Legs', {}).items():
                        entry_dict.update(**leg_dict)
                        entries.append(LegEntry(**entry_dict))

        return entries

    @classmethod
    def club_entry_exists(cls, event_id: int, club_id: int = settings.CLUB_ID) -> bool:
        params = {
            'eventid': event_id,
            'clubid': club_id
        }
        response_data = cls.make_get_request('getEventEntries', params=params)

        return bool(response_data)


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
    def set_club_entry_rights(cls, user_id: int, club_member_id: int, can_entry_self: bool, club_key: int = settings.CLUB_KEY):
        params = {
            'clubuser': club_member_id,
            'clubkey': club_key
        }

        club_member = cls.get_club_member(user_id)

        params.update(self=int(can_entry_self), other=club_member.allow_entry_other)

        response = cls.make_get_request('setClubEntryRights', params=params)

        # AllowEntrySelf just changed, so the cached roster is stale.
        cls.invalidate_club_members_cache()

        return response

    @classmethod
    def get_club_event_balance(cls, event_id: int, club_id: int = settings.CLUB_ID) -> typing.Optional[EventBalance]:
        params = {
            'eventid': event_id
        }
        response_data = cls.make_get_request('getEventBalance', params=params)

        if response_data:
            for _, club_dict in response_data['Clubs'].items():
                if club_dict['ClubID'] == club_id:
                    return EventBalance(currency=response_data.get('Currency', 'CZK'), **club_dict)

        return None

    @classmethod
    def get_club_members(cls, club_key: int = settings.CLUB_KEY) -> typing.Dict[int, ClubMember]:
        response_data = cache.get(settings.ORIS_CLUB_USER_LIST_CACHE_KEY)

        if response_data is None:
            response_data = cls.make_get_request('getClubUserList', params={'clubkey': club_key})

            if response_data:
                # An empty payload means ORIS hiccupped; caching it would starve
                # every caller for a full hour.
                cache.set(
                    settings.ORIS_CLUB_USER_LIST_CACHE_KEY,
                    response_data,
                    settings.ORIS_CLUB_USER_LIST_CACHE_TIMEOUT,
                )

        club_members = {}

        for _, club_user_dict in (response_data or {}).get('ClubMembers', {}).items():
            club_member = ClubMember(**club_user_dict)
            club_members[club_member.user_id] = club_member

        return club_members

    @classmethod
    def invalidate_club_members_cache(cls):
        cache.delete(settings.ORIS_CLUB_USER_LIST_CACHE_KEY)

    @classmethod
    def get_club_member(cls, user_id: int, club_key: int = settings.CLUB_KEY) -> typing.Optional[ClubMember]:
        return cls.get_club_members(club_key=club_key).get(int(user_id))

    @classmethod
    def get_ranking(cls, gender: Gender, date_: typing.Optional[date], sport: int = oris_choices.SPORT_OB) -> typing.List[UserRanking]:
        url = f'{settings.ORIS_URL}ranking_export?date={date_.isoformat()}&sport={sport}&gender={gender}&ranktype=8&csv=1'

        response = cls.request_with_retry(requests.get, url)
        response.raise_for_status()

        csv_data = response.text.encode(response.encoding).decode('utf-8')
        csv_reader = csv.DictReader(
            StringIO(csv_data),
            delimiter=';',
            fieldnames=['index', 'last_name', 'first_name', 'registration_number', 'points', 'coefficient', 'last_index']
        )
        next(csv_reader)    # skip header

        rankings = [UserRanking(**row, date=date_, gender=gender) for row in csv_reader]
        return [r for r in rankings if r.registration_number and (int(r.registration_number[5]) >= 5) == (gender == Gender.FEMALE)]

    @classmethod
    def get_clubs(cls) -> typing.List[Club]:
        response_data = cls.make_get_request('getCSOSClubList')

        clubs = []

        if response_data:
            for _, club_dict in response_data.items():
                clubs.append(Club(**club_dict))

        return clubs

    @classmethod
    def get_club_hosting(cls, sport: int = oris_choices.SPORT_OB, year: int = None) -> typing.List[ClubHosting]:
        params = {
            'sport': sport,
            'year': year or date.today().year
        }
        response_data = cls.make_get_request('getClubHosting', params=params)

        club_hosting = []

        if response_data:
            for _, club_hosting_dict in response_data.items():
                club_hosting.append(ClubHosting(**club_hosting_dict))

        return club_hosting

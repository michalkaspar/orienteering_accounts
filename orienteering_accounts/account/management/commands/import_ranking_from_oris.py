import logging
import typing

import redis
from django.conf import settings
from django.core.management import BaseCommand

from orienteering_accounts.oris.client import ORISClient
from orienteering_accounts.oris.models import UserRanking, Gender
from orienteering_accounts.core.utils import date as date_utils

logger = logging.getLogger(__name__)


class Command(BaseCommand):

    def handle(self, **options):

        def separate_elite_and_other_users(ranking) -> typing.Tuple[typing.List[UserRanking], typing.List[UserRanking]]:
            elite_users = []
            other_users = []

            for ranking_user in ranking:
                if ranking_user.registration_number in registration_numbers_of_elite_users:
                    ranking_user.licence = "E"
                    elite_users.append(ranking_user)
                else:
                    ranking_user.licence = "C"
                    other_users.append(ranking_user)

                if ranking_user.registration_number in registration_number_to_hosting_club_code:
                    ranking_user.hosting_club_code = registration_number_to_hosting_club_code[ranking_user.registration_number]

            #  Sort Elite users by last name
            elite_users.sort(key=lambda x: x.last_name)

            return elite_users, other_users

        date_ = date_utils.get_last_date_of_previous_month()
        cache_key = settings.REDIS_SPRINT_RELAY_RANKING_KEY.format(date=date_.isoformat())

        logger.info(f'Import ranking from ORIS to date {date_}')

        man_ranking = ORISClient.get_ranking(gender=Gender.MALE, date_=date_)
        woman_ranking = ORISClient.get_ranking(gender=Gender.FEMALE, date_=date_)
        clubs = ORISClient.get_clubs()
        club_hosting = ORISClient.get_club_hosting()

        club_id_to_code = {club.id: club.abbr for club in clubs}
        registration_number_to_hosting_club_code = {
            hosting.from_reg_no: club_id_to_code[hosting.to_club_id] for hosting in club_hosting if hosting.is_valid
        }

        registered_elite_users = ORISClient.get_registered_users(licence='E')
        registered_club_users = ORISClient.get_registered_users(club_id=settings.CLUB_ID)

        registration_numbers_of_elite_users = [user.registration_number for user in registered_elite_users]
        registration_numbers_of_club_users = [user.registration_number for user in registered_club_users]

        #  First separate the elite users from the rest of the users and order them by the last name
        elite_man_ranking_users, other_man_ranking_users = separate_elite_and_other_users(man_ranking)
        elite_woman_ranking_users, other_woman_ranking_users = separate_elite_and_other_users(woman_ranking)

        ranking_db_client = redis.Redis.from_url(f"{settings.REDIS_LOCATION}/{settings.REDIS_RANKING_DB_NUMBER}")
        ranking_db_client.delete(cache_key)

        #  We combine the rankings for man and woman into one list e.g. woman 1, man 1, woman 2, man 2, ...
        #  We don't care if the longer list will be truncated by zip
        for man_ranking_user, woman_ranking_user in zip(
            elite_woman_ranking_users + other_woman_ranking_users,
            elite_man_ranking_users + other_man_ranking_users
        ):

            if man_ranking_user.registration_number in registration_numbers_of_club_users:
                ranking_db_client.hset(
                    settings.REDIS_CLUB_USER_RANKING_KEY,
                    man_ranking_user.registration_number,
                    man_ranking_user.json()
                )

            if woman_ranking_user.registration_number in registration_numbers_of_club_users:
                ranking_db_client.hset(
                    settings.REDIS_CLUB_USER_RANKING_KEY,
                    woman_ranking_user.registration_number,
                    woman_ranking_user.json()
                )

            ranking_db_client.rpush(
                cache_key,
                woman_ranking_user.json(),
                man_ranking_user.json()
            )

        ranking_db_client.expire(cache_key, settings.REDIS_RANKING_CACHE_EXPIRATION)

        logger.info(f'Import of ranking from ORIS finished')

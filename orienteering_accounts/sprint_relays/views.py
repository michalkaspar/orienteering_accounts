import dataclasses
import json
import typing
from collections import defaultdict
from datetime import date

import redis
from django import forms
from django.conf import settings
from django.forms import Form
from django.forms.widgets import TextInput, ChoiceWidget
from django.http import HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.views import View
from django.views.generic import TemplateView

from orienteering_accounts.oris.models import UserRanking, Gender


class SprintRelaysGeneratorView(TemplateView):
    template_name = 'generator.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        ranking_db_client = redis.Redis.from_url(
            f"{settings.REDIS_LOCATION}/{settings.REDIS_RANKING_DB_NUMBER}",
            decode_responses=True
        )

        date_choices = [
            date.fromisoformat(key.replace(settings.REDIS_SPRINT_RELAY_RANKING_KEY.format(date=''), ''))
            for key in
            ranking_db_client.keys(pattern=settings.REDIS_SPRINT_RELAY_RANKING_KEY.format(date="*"))
        ]
        context['ranking_form'] = SprintRelayRankingForm(
            date_choices=[(d.isoformat(), d.strftime('%d.%m.%Y')) for d in date_choices]
        )
        return context


@dataclasses.dataclass
class Roaster:
    name: str
    runners: list[UserRanking]

    @property
    def is_valid(self) -> bool:
        return len(self.runners) == 3

    def can_add_runner(self, runner: UserRanking) -> bool:
        return len(list(filter(lambda r: r.gender == runner.gender, self.runners))) < 2


class SprintRelayRankingForm(forms.Form):
    date = forms.ChoiceField(widget=forms.Select(attrs={"class": "form-control"}), required=True, label="Ranking k datu")
    hosting = forms.CharField(widget=forms.Textarea(
        attrs={"rows":"3", "cols":"40", "class": "form-control"},
    ),
        label="Hostování",
        help_text="Zadejte hostování každého závodníka na samostatný řádek ve tvaru: Registrační číslo, klub kde hostuje. <br>Příklad: <br>TZL9308, SKM<br>TZL9754, VIC",
        required=False
    )

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        date_choices = kwargs.pop("date_choices")
        super().__init__(*args, **kwargs)
        self.fields["date"].choices = date_choices


class  SprintRelayGenerateView(View):

    def get(self, request, *args, **kwargs):
        ranking_db_client = redis.Redis.from_url(
            f"{settings.REDIS_LOCATION}/{settings.REDIS_RANKING_DB_NUMBER}",
            decode_responses=True
        )

        valid_roasters: typing.List[Roaster] = []
        roasters_for_clubs = defaultdict(list)
        hosting: dict[str, str] = {}

        try:
            for line in request.GET.get('hosting', '').split('\n'):
                if not line.strip():
                    continue
                registration_number, club_code = line.strip().split(',')
                hosting[registration_number] = club_code
        except:
            response = HttpResponse("Hostování je ve špatném formátu")
            response['HX-Retarget'] = "#error-container"
            response['HX-Swap'] = "innerHTML"
            response['HX-Trigger'] = "showError"
            return response

        sprint_relay_ranking = ranking_db_client.lrange(settings.REDIS_SPRINT_RELAY_RANKING_KEY.format(date=request.GET.get('date')), 0, -1)

        for user_ranking in map(lambda d: UserRanking.validate(json.loads(d)), sprint_relay_ranking):
            if user_ranking.registration_number in hosting:
                user_ranking.registration_number = f"{hosting[user_ranking.registration_number]}{user_ranking.registration_number[3:]}"

            club_roasters = roasters_for_clubs[user_ranking.club_code]

            roaster_found = False

            for club_roaster in club_roasters:
                if club_roaster.can_add_runner(user_ranking):
                    club_roaster.runners.append(user_ranking)

                    if club_roaster.is_valid:
                        #  Put roaster to valid roasters only once
                        valid_roasters.append(club_roaster)

                    roaster_found = True
                    break

            if not roaster_found:
                club_roasters.append(
                    Roaster(
                        name=f"{user_ranking.club_code}{len(club_roasters) + 1}",
                        runners=[user_ranking]
                    )
                )

        return render(request, 'snippets/generated_table.html', {
            'roasters': valid_roasters,
        })

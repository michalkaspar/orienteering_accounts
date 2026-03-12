import csv
import io
import json
import typing
from collections import defaultdict
from datetime import date

import redis
from django import forms
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render
from django.views import View
from django.views.generic import TemplateView
from pydantic import BaseModel

from orienteering_accounts.oris.models import UserRanking


ranking_db_client = redis.Redis.from_url(
    f"{settings.REDIS_LOCATION}/{settings.REDIS_RANKING_DB_NUMBER}",
    decode_responses=True
)

class SprintRelaysGeneratorView(TemplateView):
    template_name = 'generator.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        date_choices = sorted([
            date.fromisoformat(key.replace(settings.REDIS_SPRINT_RELAY_RANKING_KEY.format(date=''), ''))
            for key in
            ranking_db_client.keys(pattern=settings.REDIS_SPRINT_RELAY_RANKING_KEY.format(date="*"))
        ], reverse=True)
        context['ranking_form'] = SprintRelayRankingForm(
            date_choices=[(d.isoformat(), d.strftime('%d.%m.%Y')) for d in date_choices]
        )
        return context


class Roaster(BaseModel):
    name: str
    runners: typing.List[UserRanking]
    is_qualified: bool = True

    @property
    def is_valid(self) -> bool:
        return len(self.runners) == 3

    def can_add_runner(self, runner: UserRanking) -> bool:
        return len(list(filter(lambda r: r.gender == runner.gender, self.runners))) < 2


class SprintRelayRankingForm(forms.Form):
    date = forms.ChoiceField(widget=forms.Select(attrs={"class": "form-control"}), required=True, label="Ranking k datu")

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        date_choices = kwargs.pop("date_choices")
        super().__init__(*args, **kwargs)
        self.fields["date"].choices = date_choices


class SprintRelayGenerateView(View):

    def get(self, request, *args, **kwargs):
        valid_roasters: typing.List[Roaster] = []
        roasters_for_clubs = defaultdict(list)
        qualified_relays_per_club = defaultdict(int)

        sprint_relay_ranking = ranking_db_client.lrange(settings.REDIS_SPRINT_RELAY_RANKING_KEY.format(date=request.GET.get('date')), 0, -1)

        for user_ranking in map(lambda d: UserRanking.validate(json.loads(d)), sprint_relay_ranking):
            club_roasters = roasters_for_clubs[user_ranking.club_code]

            roaster_found = False

            for club_roaster in club_roasters:
                if club_roaster.can_add_runner(user_ranking):
                    club_roaster.runners.append(user_ranking)

                    if club_roaster.is_valid:
                        # Check if this club already has 5 qualified relays
                        if qualified_relays_per_club[user_ranking.club_code] < 5:
                            club_roaster.is_qualified = True
                            qualified_relays_per_club[user_ranking.club_code] += 1
                        else:
                            club_roaster.is_qualified = False
                        
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

        request.session['roasters'] = [roaster.json() for roaster in valid_roasters]

        return render(request, 'snippets/generated_table.html', {
            'roasters': valid_roasters,
        })


class SprintRelayExportView(View):

    def get(self, request, *args, **kwargs):
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';')
        writer.writerow(['poradi', 'stafeta', 'clen1', 'rank1', 'clen2', 'rank2', 'clen3', 'rank3', 'clen4', 'rank4'])

        qualified_counter = 1
        for roaster in map(lambda r: Roaster.validate(json.loads(r)), request.session['roasters']):
            # Only export qualified relays
            if not roaster.is_qualified:
                continue

            row = [qualified_counter, roaster.name]

            for runner in roaster.runners:
                row.extend([f"{runner.first_name} {runner.last_name}", runner.index])

            writer.writerow(row)
            qualified_counter += 1

        response = HttpResponse(output.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="sprint-stafety-pravo-startu.csv"'
        return response

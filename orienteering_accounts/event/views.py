from django.views.generic import ListView

from orienteering_accounts.event.models import Event


class EventsList(ListView):
    template_name = 'event/list.html'
    queryset = Event.objects.all()

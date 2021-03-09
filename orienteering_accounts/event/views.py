from django.contrib import messages
from django.views import View
from django.views.generic import ListView, DetailView
from django_filters.views import FilterView
from django.urls import reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404

from orienteering_accounts.event.filters import EventFilter
from orienteering_accounts.event.forms import EventForm
from orienteering_accounts.event.models import Event

from django.utils.translation import ugettext_lazy as _


class EventList(FilterView):
    template_name = 'event/list.html'
    queryset = Event.objects.all()
    filterset_class = EventFilter


class EventDetail(View):

    def get(self, request, pk):
        event = get_object_or_404(Event, pk=pk)
        form = EventForm(instance=event)
        return render(request, 'event/event_detail.html', {
            'event': event,
            'form': form
        })

    def post(self, request, pk):
        event = get_object_or_404(Event, pk=pk)
        form = EventForm(request.POST, instance=event)
        if not form.is_valid():
            return render(request, 'event/event_detail.html', {
                'event': event,
                'form': form
            })
        event = form.save()
        messages.add_message(
            self.request,
            messages.SUCCESS,
            _('Uloženo')
        )
        return HttpResponseRedirect(reverse('events:list'))

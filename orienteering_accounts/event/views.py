from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.views.generic import ListView, DetailView
from django_filters.views import FilterView
from django.urls import reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404

from orienteering_accounts.event.filters import EventFilter
from orienteering_accounts.event.forms import EventForm
from orienteering_accounts.event.models import Event
from orienteering_accounts.account import perms

from django.utils.translation import ugettext_lazy as _


class EventList(LoginRequiredMixin, FilterView):
    permissions_required = perms.event_view_perms
    template_name = 'event/list.html'
    queryset = Event.objects.all()
    filterset_class = EventFilter


class EventDetail(LoginRequiredMixin, View):
    permissions_required = perms.event_view_perms

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

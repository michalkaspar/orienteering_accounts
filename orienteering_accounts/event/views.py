import uuid

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.views.generic import ListView, DetailView
from django_filters.views import FilterView
from django.urls import reverse
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.shortcuts import render, get_object_or_404

from orienteering_accounts.account.models import Account
from orienteering_accounts.event.filters import EventFilter
from orienteering_accounts.event.forms import EventForm, EventEntryBillFormSet
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
        if form.cleaned_data.get('leader'):
            event.leader.leader_key = uuid.uuid4()
            event.leader.save()
        messages.add_message(
            self.request,
            messages.SUCCESS,
            _('Uloženo')
        )
        return HttpResponseRedirect(reverse('events:list'))


class EventBills(View):

    def get(self, request, pk, key):
        leader = get_object_or_404(Account, leader_key=key)
        event = get_object_or_404(Event, pk=pk)
        if event.leader.pk != leader.pk:
            raise Http404()

        if event.bills_solved:
            raise Http404()

        entries_qs = event.entries.order_by('account__registration_number')

        return render(request, 'event/event_bills.html', {
            'event': event,
            'formset': EventEntryBillFormSet(
                queryset=entries_qs
            )
        })

    def post(self, request, pk, key):
        event = get_object_or_404(Event, pk=pk)

        formset = EventEntryBillFormSet(request.POST, queryset=event.entries.all())

        if formset.is_valid():
            formset.save()
            event.bills_solved = True
            event.save(update_fields=['bills_solved'])
            return HttpResponseRedirect(reverse('events:bills_success', args=[event.pk, key]))

        render(request, 'event/event_bills.html', {
            'event': event,
            'formset': formset
        })


class EventBillsSuccess(View):

    def get(self, request, pk, key):
        leader = get_object_or_404(Account, leader_key=key)
        event = get_object_or_404(Event, pk=pk)
        if event.leader.pk != leader.pk:
            raise Http404()

        if not event.bills_solved:
            raise Http404()

        return render(request, 'event/event_bills_success.html')

import uuid
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
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
    queryset = Event.objects.order_by('-date')
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


class EventEntries(LoginRequiredMixin, View):
    permissions_required = perms.event_view_perms

    def get(self, request, pk):
        event = get_object_or_404(Event, pk=pk)
        return render(request, 'event/event_entries.html', {
            'event': event,
        })


class EventEntriesPreview(View):
    permissions_required = perms.event_view_perms

    def get(self, request, pk, key):
        leader = get_object_or_404(Account, leader_key=key)
        event = get_object_or_404(Event, pk=pk)

        if event.leader.pk != leader.pk:
            raise Http404()

        return render(request, 'event/event_entries_preview.html', {
            'event': event,
        })


class EventBills(View):

    def get(self, request, pk, key):
        leader = get_object_or_404(Account, leader_key=key)
        event = get_object_or_404(Event, pk=pk)
        if event.leader.pk != leader.pk:
            raise Http404()

        if event.bills_solved_at and event.bills_solved_at < timezone.now() - timedelta(days=14):
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
            event.bills_solved = True  # TODO deprecated
            event.processing_state = Event.ProcessingType.BILLS_SOLVED
            event.bills_solved_at = timezone.now()
            event.save(update_fields=['processing_state', 'bills_solved', 'bills_solved_at'])

            return HttpResponseRedirect(reverse('events:bills_success', args=[event.pk, key]))

        return render(request, 'event/event_bills.html', {
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

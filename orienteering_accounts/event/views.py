import uuid
from datetime import timedelta
from decimal import Decimal

import requests
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import QuerySet
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
from orienteering_accounts.oris.client import ORISClient

from django.utils.translation import ugettext_lazy as _


class EventList(LoginRequiredMixin, FilterView):
    permissions_required = perms.event_view_perms
    template_name = 'event/list.html'
    filterset_class = EventFilter

    def get_queryset(self) -> QuerySet[Event]:
        return Event.objects.filter(
            date__gte=timezone.now() - timedelta(days=180)
        ).order_by('-date')


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
        if form.cleaned_data.get('leader') and not event.leader.leader_key:
            event.leader.leader_key = uuid.uuid4()
            event.leader.save()
        if 'leader' in form.changed_data and event.leader:
            event.send_leader_assigned_email()
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
            'email_recipients': ', '.join(filter(None, event.entries.values_list('account__email', flat=True)))
        })


class EventEntriesPreview(View):
    permissions_required = perms.event_view_perms

    def get(self, request, pk, key):
        get_object_or_404(Account, leader_key=key)
        event = get_object_or_404(Event, pk=pk)

        return render(request, 'event/event_entries_preview.html', {
            'event': event,
            'email_recipients': ', '.join(filter(None, event.entries.values_list('account__email', flat=True)))
        })


class EventBills(View):

    def get(self, request, pk, key):
        get_object_or_404(Account, leader_key=key)
        event = get_object_or_404(Event, pk=pk)

        # Get sorting parameters from query string
        sort_by = request.GET.get('sort', 'account__registration_number')
        order = request.GET.get('order', 'asc')
        
        # Define allowed sort fields to prevent SQL injection
        allowed_sorts = {
            'name': 'account__last_name',
            'registration_number': 'account__registration_number',
            'category': 'category_name',
            'fee': 'fee',
        }
        
        # Validate and get the sort field
        sort_field = allowed_sorts.get(sort_by, 'account__registration_number')
        
        # Apply order direction
        if order == 'desc':
            sort_field = f'-{sort_field}'
        
        entries_qs = event.entries.order_by(sort_field)

        formset = EventEntryBillFormSet(queryset=entries_qs)
        local_debt_sum = sum(form.initial['debt'] for form in formset.forms)

        try:
            event_balance = ORISClient.get_club_event_balance(event.oris_id)
        except requests.RequestException:
            event_balance = None

        debt_mismatch = event_balance is not None and abs(local_debt_sum - event_balance.to_be_paid) > Decimal('1')

        return render(request, 'event/event_bills.html', {
            'event': event,
            'formset': formset,
            'current_sort': sort_by,
            'current_order': order,
            'event_balance': event_balance,
            'local_debt_sum': local_debt_sum,
            'debt_mismatch': debt_mismatch,
        })

    def post(self, request, pk, key):
        event = get_object_or_404(Event, pk=pk)

        formset = EventEntryBillFormSet(request.POST, queryset=event.entries.all())

        if formset.is_valid():
            formset.save()
            event.bills_solved = True
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

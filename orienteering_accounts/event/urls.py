from django.urls import path

from orienteering_accounts.event.views import EventsList

app_name = 'events'

urlpatterns = [
    path('', EventsList.as_view(), name='list'),
]

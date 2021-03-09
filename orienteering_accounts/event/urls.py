from django.urls import path

from orienteering_accounts.event.views import EventList, EventDetail

app_name = 'events'

urlpatterns = [
    path('', EventList.as_view(), name='list'),
    path('<int:pk>/', EventDetail.as_view(), name='detail'),
]

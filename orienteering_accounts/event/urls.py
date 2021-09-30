from django.urls import path

from orienteering_accounts.event.views import EventList, EventDetail, EventBills, EventBillsSuccess, EventEntries, EventEntriesPreview

app_name = 'events'

urlpatterns = [
    path('', EventList.as_view(), name='list'),
    path('<int:pk>/', EventDetail.as_view(), name='detail'),
    path('<int:pk>/entries', EventEntries.as_view(), name='entries'),
    path('<int:pk>/entries/<uuid:key>/', EventEntriesPreview.as_view(), name='entries_preview'),
    path('<int:pk>/bills/<uuid:key>/', EventBills.as_view(), name='bills'),
    path('<int:pk>/bills/<uuid:key>/success/', EventBillsSuccess.as_view(), name='bills_success'),
]

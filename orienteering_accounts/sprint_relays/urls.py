from django.urls import path

from orienteering_accounts.sprint_relays.views import SprintRelaysGeneratorView, SprintRelayGenerateView, \
    SprintRelayExportView

app_name = 'sprint_relays'

urlpatterns = [
    path('', SprintRelaysGeneratorView.as_view(), name='generator'),
    path('generate/', SprintRelayGenerateView.as_view(), name='generate'),
    path('export/', SprintRelayExportView.as_view(), name='export'),
]

from datetime import datetime

from django.views.generic import UpdateView, TemplateView

from orienteering_accounts.core.models import Settings


class SettingsEdit(UpdateView):
    model = Settings
    fields = ['club_membership_deadline']
    template_name = 'core/settings_update.html'

    def get_object(self, *args, **kwargs):
        return self.model.objects.get_or_create(
            id=1,
            defaults={'club_membership_deadline': datetime(datetime.today().year, 2, 28, 23, 59, 59)}
        )[0]


class PrivacyPolicyView(TemplateView):
    template_name = 'core/privacy_policy.html'


class TermsOfServiceView(TemplateView):
    template_name = 'core/terms_of_service.html'


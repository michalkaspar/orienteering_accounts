from django import forms
from datetime import date

from orienteering_accounts.account.models import Account
from orienteering_accounts.event.models import Event


class EventForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.read_only():
            for f in self.fields.values():
                f.disabled = True
        else:
            self.fields['leader'].queryset = Account.objects.exclude(event__isnull=False)

    def read_only(self):
        return self.instance.date <= date.today()

    def is_valid(self):
        if not super().is_valid():
            return False
        return self.instance.handled or self.instance.leader is None

    class Meta:
        model = Event
        fields = ['handled', 'leader']

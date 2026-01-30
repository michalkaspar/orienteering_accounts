from django.apps import AppConfig


class AccountConfig(AppConfig):
    name = 'orienteering_accounts.account'
    verbose_name = 'Account'

    def ready(self):
        # Import signals to register them
        import orienteering_accounts.account.signals

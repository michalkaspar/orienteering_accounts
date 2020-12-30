from unittest import mock

from django.conf import settings
from django.test import TestCase
from django.core.management import call_command

from orienteering_accounts.account.models import Account


ORIS_REGISTER_USERS_RESPONSE_DATA = {
    "Reg_174932":{
        "RegNo": "TZL6666",
        "UserID": "390",
        "Lic": "C",
        "FirstName": "Chuck",
        "LastName": "Norris",
        "SI": "7207026",
        "Paid": "1",
        "ClubID": settings.CLUB_ID,
        "Gender": "M",
        "Born": "70",
        "Fee": "60"
    },
    "Reg_174933":{
        "RegNo": "TZL9999",
        "UserID": "377",
        "Lic": "C",
        "FirstName": "Rocky",
        "LastName": "Balboa",
        "SI": "980377",
        "Paid": "1",
        "ClubID": settings.CLUB_ID,
        "Gender": "M",
        "Born": "65",
        "Fee": "60"
    }
}


class ImportTestCase(TestCase):

    @mock.patch('orienteering_accounts.oris.client.ORISClient.make_get_request',
                return_value=ORIS_REGISTER_USERS_RESPONSE_DATA)
    def test_import_accounts_from_oris(self, mock_get_registered_users):
        call_command('import_accounts_from_oris')
        mock_get_registered_users.assert_called()
        self.assertEquals(Account.objects.count(), 2)

from unittest import mock

from django.conf import settings
from django.test import TestCase
from django.core.management import call_command

from orienteering_accounts.account.models import Account, Role


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


ORIS_CLUB_USER_LIST_RESPONSE_DATA = {
    "ClubMembers": {
        "ClubMember_1": {
            "ID": "11", "UserID": "390", "RegNum": "TZL6666",
            "AllowEntrySelf": 1, "AllowEntryOther": 0,
            "MemberFrom": "2026-01-01", "MemberTo": "2026-12-31", "Valid": 1,
            "Username": "tzl6666", "FirstName": "Chuck", "LastName": "Norris",
            "Email": "chuck@example.com",
            "AddressGPSLat": 50.0, "AddressGPSLon": 14.0,
            "Street": "Ulice 1", "City": "Praha", "Zip": "11000", "Country": "CZ",
            "Birthday": "1970-01-01", "Phone": "+420000000000", "Gender": "M",
            "PersNum": "700101/0000", "Nationality": "CZ",
            "SI": "7207026", "SISport": 0, "SIType": 1,
            "SI2": "", "SISport2": 0, "SIType2": 0,
            "SI3": "", "SISport3": 0, "SIType3": 0,
            "IOFID": 0, "ShowFullCalendar": 0, "MyRegionsInCalendar": "",
            "DoNotReceiveEmailsFromORIS": 0, "NotifyAboutFeedbackByEmail": 0,
        },
        "ClubMember_2": {
            "ID": "12", "UserID": "377", "RegNum": "TZL9999",
            "AllowEntrySelf": 1, "AllowEntryOther": 0,
            "MemberFrom": "2026-01-01", "MemberTo": "2026-12-31", "Valid": 1,
            "Username": "tzl9999", "FirstName": "Rocky", "LastName": "Balboa",
            "Email": "rocky@example.com",
            "AddressGPSLat": 50.0, "AddressGPSLon": 14.0,
            "Street": "Ulice 2", "City": "Praha", "Zip": "11000", "Country": "CZ",
            "Birthday": "1965-01-01", "Phone": "+420000000001", "Gender": "M",
            "PersNum": "650101/0000", "Nationality": "CZ",
            "SI": "980377", "SISport": 0, "SIType": 1,
            "SI2": "", "SISport2": 0, "SIType2": 0,
            "SI3": "", "SISport3": 0, "SIType3": 0,
            "IOFID": 0, "ShowFullCalendar": 0, "MyRegionsInCalendar": "",
            "DoNotReceiveEmailsFromORIS": 0, "NotifyAboutFeedbackByEmail": 0,
        },
    }
}


def _oris_response(endpoint, params=None, **kwargs):
    if endpoint == 'getClubUserList':
        return ORIS_CLUB_USER_LIST_RESPONSE_DATA
    return ORIS_REGISTER_USERS_RESPONSE_DATA


class ImportTestCase(TestCase):

    @mock.patch('orienteering_accounts.account.models.Account.add_to_google_workspace_group')
    @mock.patch('orienteering_accounts.account.models.Account.send_account_created_info_email')
    @mock.patch('orienteering_accounts.oris.client.ORISClient.make_get_request',
                side_effect=_oris_response)
    def test_import_accounts_from_oris(self, mock_get_registered_users, mock_email, mock_group):
        # upsert_from_oris assigns this role to every newly created account;
        # it is normally seeded in the production database, not by a migration.
        Role.objects.create(name='Člen')
        call_command('import_accounts_from_oris')
        mock_get_registered_users.assert_called()
        self.assertEqual(Account.objects.count(), 2)

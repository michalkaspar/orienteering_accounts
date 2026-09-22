def club_member_payload(user_id, club_member_id, registration_number, email, **overrides):
    payload = {
        'ID': club_member_id,
        'UserID': str(user_id),
        'RegNum': registration_number,
        'AllowEntrySelf': 1,
        'AllowEntryOther': 0,
        'MemberFrom': '2026-01-01',
        'MemberTo': '2026-12-31',
        'Valid': 1,
        'Username': registration_number.lower(),
        'FirstName': 'Chuck',
        'LastName': 'Norris',
        'Email': email,
        'AddressGPSLat': 50.0,
        'AddressGPSLon': 14.0,
        'Street': 'Ulice 1',
        'City': 'Praha',
        'Zip': '11000',
        'Country': 'CZ',
        'Birthday': '1970-01-01',
        'Phone': '+420000000000',
        'Gender': 'M',
        'PersNum': '700101/0000',
        'Nationality': 'CZ',
        'SI': '7207026',
        'SISport': 0,
        'SIType': 1,
        'SI2': '',
        'SISport2': 0,
        'SIType2': 0,
        'SI3': '',
        'SISport3': 0,
        'SIType3': 0,
        'IOFID': 0,
        'ShowFullCalendar': 0,
        'MyRegionsInCalendar': '',
        'DoNotReceiveEmailsFromORIS': 0,
        'NotifyAboutFeedbackByEmail': 0,
    }
    payload.update(overrides)
    return payload


def club_user_list_response(*members):
    return {'ClubMembers': {f'ClubMember_{member["ID"]}': member for member in members}}

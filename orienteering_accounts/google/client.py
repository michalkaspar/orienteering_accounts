import base64
import json
import typing

from django.conf import settings
from google.oauth2 import service_account
from googleapiclient.discovery import build, Resource


class GoogleAPIClient:


    def __init__(self):
        service_account_info = json.loads(base64.b64decode(settings.GOOGLE_SERVICE_ACCOUNT_CREDENTIALS))
        credentials = service_account.Credentials.from_service_account_info(service_account_info)
        self.credentials = credentials.with_subject(settings.GOOGLE_SERVICE_ACCOUNT_CREDENTIALS_SUBJECT)

    def _get_service(self, service_name, version, scopes: typing.List[str]) -> Resource:
        credentials = self.credentials.with_scopes(scopes)
        return build(service_name, version, credentials=credentials)

    @property
    def members_service(self) -> Resource:
        scopes = ['https://www.googleapis.com/auth/admin.directory.group.member']
        return self._get_service('admin', 'directory_v1', scopes=scopes)

    def add_member(self, member_email: str, group_email: str = settings.GOOGLE_GROUP_MEMBERS) -> None:
        self.members_service.members().insert(groupKey=group_email, body={'email': member_email}).execute()


client = GoogleAPIClient()

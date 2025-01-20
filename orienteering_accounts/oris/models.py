import typing

from datetime import datetime, date
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, validator


class Gender(str, Enum):
    MALE = 'M'
    FEMALE = 'F'


class RegisteredUser(BaseModel):
    registration_number: str = Field(alias='RegNo')
    oris_id: int = Field(alias='UserID')
    licence: str = Field(alias='Lic')
    first_name: str = Field(alias='FirstName')
    last_name: str = Field(alias='LastName')
    si: str = Field(alias='SI')
    oris_paid: int = Field(alias='Paid')
    oris_club_id: int = Field(alias='ClubID')
    gender: Gender = Field(alias='Gender')
    born_year: int = Field(alias='Born')
    oris_fee: int = Field(alias='Fee')


class ClubMember(BaseModel):
    id: int = Field(alias='ID')
    user_id: int = Field(alias='UserID')
    registration_number: str = Field(alias='RegNum')
    allow_entry_self: int = Field(alias='AllowEntrySelf')
    allow_entry_other: int = Field(alias='AllowEntryOther')
    member_from: date = Field(alias='MemberFrom')
    member_to: date = Field(alias='MemberTo')
    valid: int = Field(alias='Valid')
    username: str = Field(alias='Username')
    first_name: str = Field(alias='FirstName')
    last_name: str = Field(alias='LastName')
    email: str = Field(alias='Email')
    address_gps_lat: float = Field(alias='AddressGPSLat')
    address_gps_lon: float = Field(alias='AddressGPSLon')
    street: str = Field(alias='Street')
    city: str = Field(alias='City')
    zip_code: str = Field(alias='Zip')
    country: str = Field(alias='Country')
    birthday: date = Field(alias='Birthday')
    phone: str = Field(alias='Phone')
    gender: str = Field(alias='Gender')
    personal_number: str = Field(alias='PersNum')
    nationality: str = Field(alias='Nationality')
    si: str = Field(alias='SI')
    si_sport: int = Field(alias='SISport')
    si_type: int = Field(alias='SIType')
    si2: str = Field(alias='SI2')
    si_sport2: int = Field(alias='SISport2')
    si_type2: int = Field(alias='SIType2')
    si3: str = Field(alias='SI3')
    si_sport3: int = Field(alias='SISport3')
    si_type3: int = Field(alias='SIType3')
    iof_id: int = Field(alias='IOFID')
    show_full_calendar: int = Field(alias='ShowFullCalendar')
    my_regions_in_calendar: str = Field(alias='MyRegionsInCalendar')
    do_not_receive_emails_from_oris: int = Field(alias='DoNotReceiveEmailsFromORIS')
    notify_about_feedback_by_email: int = Field(alias='NotifyAboutFeedbackByEmail')


class Organizer(BaseModel):
    oris_id: int = Field(alias='ID')
    abbr: str = Field(alias='Abbr')
    name: str = Field(alias='Name')


class Discipline(BaseModel):
    oris_id: int = Field(alias='ID')
    abbr: str = Field(alias='ShortName')
    name: str = Field(alias='NameCZ')


class Level(BaseModel):
    oris_id: int = Field(alias='ID')
    abbr: str = Field(alias='ShortName')
    name: str = Field(alias='NameCZ')


class SIType(BaseModel):
    oris_id: int = Field(alias='ID')
    name: str = Field(alias='Name')


class Event(BaseModel):
    oris_id: int = Field(alias='ID')
    name: str = Field(alias='Name')
    date: str = Field(alias='Date')
    organizer_1: Organizer = Field(alias='Org1')
    organizer_2: typing.Any = Field(alias='Org2')
    region: str = Field(alias='Region')
    discipline: Discipline = Field(alias='Discipline')
    level: Level = Field(alias='Level')
    ranking: Decimal = Field(alias='Ranking')
    si_type: SIType = Field(alias='SIType')
    cancelled: bool = Field(alias='Cancelled')
    gps_lat: str = Field(alias='GPSLat')
    gps_lon: str = Field(alias='GPSLon')
    venue: str = Field(alias='Place')
    oris_version: int = Field(alias='Version')
    oris_classes_last_modified_timestamp: typing.Optional[int] = Field(alias='ClassesLastModifiedTimeStamp')
    oris_services_last_modified_timestamp: typing.Optional[int] = Field(alias='ServicesLastModifiedTimeStamp')
    oris_parent_id: typing.Optional[int] = Field(alias='ParentID')
    status: typing.Optional[str] = Field(alias='Status', default='')
    ob_postupy: typing.Optional[str] = Field(alias='OBPostupy')
    categories_data: typing.Any = Field(alias='Classes', default={})
    entry_date_1: typing.Optional[str] = Field(alias='EntryDate1')
    entry_date_2: typing.Optional[str] = Field(alias='EntryDate2')
    entry_date_3: typing.Optional[str] = Field(alias='EntryDate3')
    entry_bank_account: typing.Optional[str] = Field(alias='EntryBankAccount', default='')
    links: typing.Any = Field(alias='Links', default={})
    additional_services: typing.Any = Field(alias='Services', default={})

    @validator('entry_date_1', 'entry_date_2', 'entry_date_3')
    def never_empty(cls, v: str) -> typing.Optional[str]:
        if not v:
            return None
        return v


class BaseEntry(BaseModel):
    oris_category_id: int = Field(alias='ClassID')
    category_name: str = Field(alias='ClassDesc')
    oris_created: datetime = Field(alias='CreatedDateTime')
    oris_updated: typing.Optional[str] = Field(alias='UpdatedDateTime')

    @property
    def is_valid(self) -> bool:
        return NotImplemented

    @property
    def account_kwargs(self) -> dict:
        return NotImplemented

    def get_additional_services(self, additional_services: typing.Dict[int, dict]) -> list:
        pass


class Entry(BaseEntry):
    oris_id: int = Field(alias='ID')
    oris_user_id: typing.Optional[int] = Field(alias='UserID')
    fee: int = Field(alias='Fee')
    rent_si: typing.Optional[bool] = Field(alias='RentSI')
    oris_club_note: typing.Optional[str] = Field(alias='ClubNote')

    @validator('oris_updated')
    def never_empty(cls, v: str) -> typing.Optional[str]:
        if not v:
            return None
        return v

    @property
    def is_valid(self) -> bool:
        return self.oris_user_id is not None

    @property
    def account_kwargs(self) -> dict:
        return dict(oris_id=self.oris_user_id)

    def get_additional_services(self, additional_services: typing.Dict[int, dict]) -> list:
        return additional_services.get(self.oris_user_id, [])


class LegEntry(BaseEntry):
    registration_number: typing.Optional[str] = Field(alias='RegNo')

    @property
    def is_valid(self) -> bool:
        return self.registration_number is not None

    @property
    def account_kwargs(self) -> dict:
        return dict(registration_number=self.registration_number)

    def get_additional_services(self, additional_services: typing.Dict[int, typing.List[dict]]) -> list:
        if not self.is_valid:
            return []
        return [service_dict for service_dicts in additional_services.values() for service_dict in service_dicts if service_dict['RegNo'] == self.registration_number]


class Result(BaseModel):
    class_name: str = Field(alias='ClassDesc')
    registration_number: str = Field(alias='RegNo')
    time: typing.Optional[str] = Field(alias='Time')


class EventBalance(BaseModel):
    to_be_paid: Decimal = Field(alias='ToBePaid')
    payment_vs: typing.Optional[str] = Field(alias='PaymentVS')
    currency: str

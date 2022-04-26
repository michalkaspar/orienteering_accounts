import typing
from datetime import datetime
from decimal import Decimal
from enum import Enum

from django.utils.functional import cached_property
from pydantic import BaseModel, Field, validator

from orienteering_accounts.oris.client import ORISClient


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


class Entry(BaseModel):
    oris_id: int = Field(alias='ID')
    oris_category_id: int = Field(alias='ClassID')
    category_name: str = Field(alias='ClassDesc')
    oris_user_id: typing.Optional[int] = Field(alias='UserID')
    fee: int = Field(alias='Fee')
    oris_created: datetime = Field(alias='CreatedDateTime')
    oris_updated: typing.Optional[str] = Field(alias='UpdatedDateTime')
    rent_si: typing.Optional[bool] = Field(alias='RentSI')
    oris_club_note: typing.Optional[str] = Field(alias='ClubNote')

    @validator('oris_updated')
    def never_empty(cls, v: str) -> typing.Optional[str]:
        if not v:
            return None
        return v


class Result(BaseModel):
    class_name: str = Field(alias='ClassDesc')
    registration_number: str = Field(alias='RegNo')


class EventBalance(BaseModel):
    to_be_paid: Decimal = Field(alias='ToBePaid')
    payment_vs: typing.Optional[str] = Field(alias='PaymentVS')

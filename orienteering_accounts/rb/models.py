import typing

from pydantic import BaseModel


class TransactionAmount(BaseModel):
    value: float
    currency: str


class BankTransactionCode(BaseModel):
    code: str


class CreditorReferenceInformation(BaseModel):
    variable: str = None
    constant: str = None
    specific: str = None


class RemittanceInformation(BaseModel):
    unstructured: str = None
    creditorReferenceInformation: CreditorReferenceInformation = None
    originatorMessage: str


class OrganisationIdentification(BaseModel):
    bankCode: str


class Account(BaseModel):
    accountNumber: str


class CounterParties(BaseModel):
    organisationIdentification: OrganisationIdentification
    account: Account
    name: str = None


class RelatedParties(BaseModel):
    counterParty: CounterParties = None


class TransactionDetails(BaseModel):
    references: dict
    relatedParties: RelatedParties
    remittanceInformation: RemittanceInformation


class TransactionEntryDetails(BaseModel):
    transactionDetails: TransactionDetails


class Transaction(BaseModel):
    entryReference: str
    amount: TransactionAmount
    creditDebitIndication: str
    bookingDate: str
    valueDate: str
    bankTransactionCode: BankTransactionCode
    entryDetails:TransactionEntryDetails

    @property
    def variable_symbol(self) -> typing.Union[str, None]:
        try:
            return self.entryDetails.transactionDetails.remittanceInformation.creditorReferenceInformation.variable
        except AttributeError:
            return None

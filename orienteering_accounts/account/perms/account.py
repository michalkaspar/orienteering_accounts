from orienteering_accounts.account.choices import *


def view_payment_period_list(account):
    return account.ifperm(PERMISSION_VIEW_PAYMENT_PERIOD_LIST)


def create_payment_period(account):
    return account.ifperm(PERMISSION_EDIT_PAYMENT_PERIOD)


def edit_payment_period(account):
    return account.ifperm(PERMISSION_EDIT_PAYMENT_PERIOD)


def view_payment_period(account):
    return account.ifperm(PERMISSION_VIEW_PAYMENT_PERIOD)


payment_period_create_perms = [create_payment_period]
payment_period_edit_perms = [edit_payment_period]
payment_period_view_perms = [
    view_payment_period_list,
    view_payment_period
]


def view_account_list(account):
    return account.ifperm(PERMISSION_VIEW_ACCOUNT_LIST)


def edit_account(account):
    return account.ifperm(PERMISSION_EDIT_ACCOUNT)


def view_account(account):
    return account.ifperm(PERMISSION_VIEW_ACCOUNT)


account_edit_perms = [edit_account]
account_view_perms = [
    view_account,
    view_account_list
]


def add_transaction(account):
    return account.ifperm(PERMISSION_ADD_TRANSACTION)


def edit_transaction(account):
    return account.ifperm(PERMISSION_EDIT_TRANSACTION)


transaction_create_perms = [add_transaction]

transaction_edit_perms = [edit_transaction]


def add_role(account):
    return account.ifperm(PERMISSION_ADD_ROLE)


def change_role(account):
    return account.ifperm(PERMISSION_CHANGE_ROLE)


def delete_role(account):
    return account.ifperm(PERMISSION_DELETE_ROLE)


def view_role(account):
    return account.ifperm(PERMISSION_VIEW_ROLE)


role_add_perms = [add_role]
role_edit_perms = [change_role, add_role]
role_delete_perms = [change_role]
role_view_perms = [add_role, change_role, delete_role, view_role]


def view_change_log(account):
    return account.ifperm(PERMISSION_VIEW_CHANGE_LOG)


change_log_view_perms = [view_change_log]


def view_bank_transaction_list(account):
    return account.ifperm(PERMISSION_VIEW_BANK_TRANSACTION_LIST)


bank_transaction_view_perms = [view_bank_transaction_list]

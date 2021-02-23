from orienteering_accounts.account.choices import *


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


transaction_create_perms = [add_transaction]


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
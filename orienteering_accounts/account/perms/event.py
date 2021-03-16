from orienteering_accounts.account.choices import *


def view_event_list(account):
    return account.ifperm(PERMISSION_VIEW_EVENT_LIST)


def edit_event(account):
    return account.ifperm(PERMISSION_EDIT_EVENT)


def view_event(account):
    return account.ifperm(PERMISSION_VIEW_EVENT)


event_edit_perms = [edit_event]
event_view_perms = [
    view_event,
    view_event_list
]

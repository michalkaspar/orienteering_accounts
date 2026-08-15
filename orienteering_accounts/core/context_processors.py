from orienteering_accounts.core.changelog_data import CHANGELOG_ENTRIES, changelog_sort_key


def current_version(request):
    if not CHANGELOG_ENTRIES:
        return {'current_version': None}

    return {'current_version': max(CHANGELOG_ENTRIES, key=changelog_sort_key)['version']}

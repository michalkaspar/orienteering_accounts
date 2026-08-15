from orienteering_accounts.core.changelog_data import CHANGELOG_ENTRIES


def current_version(request):
    if not CHANGELOG_ENTRIES:
        return {'current_version': None}

    return {'current_version': max(CHANGELOG_ENTRIES, key=lambda entry: entry['date'])['version']}

# ORIS API Traffic Reduction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cut ORIS API traffic from ~60 000 requests/day to ~1 300 without reducing the freshness of club entries.

**Architecture:** Three independent levers. Cache the two whole-list endpoints (`getClubUserList`, `getRegistration`) so they are fetched once per hour instead of once per record. Stop calling ORIS on every transaction save by fixing a signal that contradicts its own documentation. Replace blind per-event polling with change detection driven by markers (`Version`, `ClubEntryCount`, `ClubEntryLastModifiedTimeStamp`) that `getEventList` already returns when passed `myClubId`.

**Tech Stack:** Django 3.2.18, pydantic 1.7.2, django-redis 4.11.0, model-bakery 1.15.0, freezegun 1.0.0, Python 3.9 (in Docker).

**Spec:** `docs/superpowers/specs/2026-09-22-oris-api-traffic-reduction-design.md`

## Global Constraints

- **Test command:** `docker compose -f .superpowers/sdd/2026-09-22-oris-api-traffic-reduction/docker-compose.test.yml run --rm web python manage.py test <target>`, with `DOCKER_CONFIG` exported to the scratchpad docker dir. The host Python is 3.13 and cannot run Django 3.2 (`No module named 'cgi'`), so tests only run in Docker.
- **Why that compose file:** the sandbox blocks every `.env*` path, so the project's own `docker-compose.yml` (which declares `env_file: - .env`) cannot start and the repo root cannot be used as a build context. The workspace copy declares no `env_file`, injects throwaway SECRET_KEY / Google credentials / ORIS identity, and builds from a minimal scratchpad context. Never commit it; it lives in the git-ignored SDD workspace.
- **Baseline:** 103 tests, 6 errors before Task 1; 101 tests, all passing after it.
- **No formatting-only changes.** Per `CLAUDE.md`, touch only lines that are functionally necessary. Do not reflow, reindent, or restyle surrounding code, including existing trailing whitespace.
- **No Claude attribution in commits.** Per `CLAUDE.md`, never add a `Co-Authored-By: Claude` trailer or a "Generated with Claude Code" line.
- **Commit style:** `type(scope): Capitalised summary`, matching recent history (`fix(oris): Retry throttled ORIS API requests instead of failing`).
- **Settings live in** `orienteering_accounts/settings/base.py`. Add new constants next to the existing `ORIS_*` block around line 270.
- **ORIS is a third party under load.** No task may add an ORIS request to a code path that runs per record. Requests belong in per-run code paths only.

## File Structure

| File | Responsibility | Tasks |
| --- | --- | --- |
| `orienteering_accounts/oris/client.py` | All ORIS HTTP access: caching, rate cap, request counting | 2, 3, 5, 7, 8 |
| `orienteering_accounts/oris/models.py` | Pydantic shapes of ORIS payloads | 6 |
| `orienteering_accounts/oris/tests/fixtures.py` | **New.** Reusable ORIS payload builders | 2 |
| `orienteering_accounts/oris/tests/test_client.py` | Client behaviour: retry, cache, rate cap | 2, 3, 5 |
| `orienteering_accounts/account/signals.py` | Balance-driven entry rights and emails | 4 |
| `orienteering_accounts/account/services.py` | Bank transaction batch processing | 3 |
| `orienteering_accounts/event/models.py` | Event sync, change detection, reconciliation | 6, 8, 9 |
| `orienteering_accounts/event/migrations/0014_*.py` | **New.** Club entry markers and sync timestamp | 6 |
| `orienteering_accounts/event/tests/fixtures.py` | Event payload fixtures | 6, 8 |
| `orienteering_accounts/settings/base.py` | New cache, budget and window constants | 2, 3, 5, 8, 9 |
| `orienteering_accounts/account/tests/test_import.py`, `account/tests/test_models.py`, `entry/tests/test_models.py` | Pre-existing test breakage repaired so later tasks have a gate | 1 |

---

### Task 1: Get the test suite green

The measured baseline is **103 tests, 6 errors**, all failing on the code as
committed, independent of configuration. Every later task verifies itself with
"the full suite passes", so that gate has to mean something first.

| Failing test | Root cause |
| --- | --- |
| `event/tests/test_import.py` | `call_command('import_events_from_oris')` — that command does not exist; `event/management/commands/` holds only `process_events.py` |
| `event/tests/test_refresh.py` | same |
| `account/tests/test_import.py` | the mock returns the registration payload for *every* call, so `get_club_member` does `payload['ClubMembers']` and raises `KeyError` |
| `account/tests/test_models.py::test_get_accounts_without_paid_club_membership` | calls `Account.get_accounts_without_paid_club_membership(deadline)`, which was removed and replaced by `get_accounts_to_remove_entry_rights_in_oris()` with different arguments and semantics |
| `entry/tests/test_models.py::test_creates_placeholder_entry_with_service_transactions` | `debt_init` -> `did_not_start` -> `Event.results` is unmocked and issues a **live ORIS HTTP request** |
| `event/tests/test_update_entries.py::test_orphan_service_order_creates_services_only_entry` | the same live `getEventResults` call |

**Files:**
- Modify: `orienteering_accounts/event/tests/test_import.py`
- Delete: `orienteering_accounts/event/tests/test_refresh.py`
- Modify: `orienteering_accounts/account/tests/test_import.py`
- Modify: `orienteering_accounts/account/tests/test_models.py`
- Modify: `orienteering_accounts/entry/tests/test_models.py`
- Modify: `orienteering_accounts/event/tests/test_update_entries.py`

**Interfaces:**
- Consumes: nothing.
- Produces: a green suite, so every later task can use "all tests pass" as its gate.

- [ ] **Step 1: Confirm the baseline**

Run: `docker compose -f .superpowers/sdd/2026-09-22-oris-api-traffic-reduction/docker-compose.test.yml run --rm web python manage.py test orienteering_accounts`

Expected: `Ran 103 tests`, `FAILED (errors=6)`, and the six names above. If the
set differs, stop and report before changing anything.

- [ ] **Step 2: Point the event import test at the real command**

`process_events` calls `Event.import_from_oris()`, then `Event.refresh_from_oris()`,
then three email senders. The test only cares about the import, so call the model
method directly. Replace the whole body of `orienteering_accounts/event/tests/test_import.py`:

```python
from unittest import mock

from django.test import TestCase

from orienteering_accounts.event.models import Event
from orienteering_accounts.event.tests import fixtures


class ImportTestCase(TestCase):

    @mock.patch('orienteering_accounts.event.models.Event.update_entries')
    @mock.patch('orienteering_accounts.event.models.Event._update_exchange_rate')
    @mock.patch('orienteering_accounts.event.models.Event._refresh_from_oris')
    @mock.patch('orienteering_accounts.oris.client.ORISClient.make_get_request',
                return_value=fixtures.ORIS_EVENTS_RESPONSE_DATA)
    def test_import_events_from_oris(self, mock_get_events, mock_refresh, mock_exchange_rate, mock_update_entries):
        Event.import_from_oris()

        mock_get_events.assert_called()
        self.assertEqual(Event.objects.count(), 1)
```

The fixture event is dated 2020-10-25, so today's code skips the expensive
per-event branch entirely. The three extra patches make that explicit and, more
importantly, keep the test honest after Task 8: from then on a first-time import
does call `_refresh_from_oris()` even for a past event, and the single
`make_get_request` mock would feed it the *list* payload and blow up with a
`ValidationError`. Patch it here so that never happens.

- [ ] **Step 3: Delete the refresh test**

`test_refresh.py` holds one test whose assertions are entirely commented out
behind a `# TODO mock get event entries`. It covers `refresh_events_from_oris`,
a command that does not exist, and Task 8 deletes the `refresh_from_oris()`
method it was written for. Deleting it removes dead weight rather than migrating
a test that asserts nothing.

```bash
git rm orienteering_accounts/event/tests/test_refresh.py
```

- [ ] **Step 4: Give the account import test an endpoint-aware mock**

The single `return_value` feeds the registration payload to every ORIS call,
including the `getClubUserList` inside `Account.upsert_from_oris`. Replace the
`ImportTestCase` class in `orienteering_accounts/account/tests/test_import.py`
(keep `ORIS_REGISTER_USERS_RESPONSE_DATA` exactly as it is):

```python
ORIS_CLUB_USER_LIST_RESPONSE_DATA = {
    "ClubMembers": {
        "ClubMember_1": {
            "ID": "11", "UserID": "390", "RegNum": "TZL6666",
            "AllowEntrySelf": 1, "AllowEntryOther": 0,
            "MemberFrom": "2026-01-01", "MemberTo": "2026-12-31", "Valid": 1,
            "Username": "tzl6666", "FirstName": "Chuck", "LastName": "Norris",
            "Email": "chuck@example.com",
            "AddressGPSLat": 50.0, "AddressGPSLon": 14.0,
            "Street": "Ulice 1", "City": "Praha", "Zip": "11000", "Country": "CZ",
            "Birthday": "1970-01-01", "Phone": "+420000000000", "Gender": "M",
            "PersNum": "700101/0000", "Nationality": "CZ",
            "SI": "7207026", "SISport": 0, "SIType": 1,
            "SI2": "", "SISport2": 0, "SIType2": 0,
            "SI3": "", "SISport3": 0, "SIType3": 0,
            "IOFID": 0, "ShowFullCalendar": 0, "MyRegionsInCalendar": "",
            "DoNotReceiveEmailsFromORIS": 0, "NotifyAboutFeedbackByEmail": 0,
        },
        "ClubMember_2": {
            "ID": "12", "UserID": "377", "RegNum": "TZL9999",
            "AllowEntrySelf": 1, "AllowEntryOther": 0,
            "MemberFrom": "2026-01-01", "MemberTo": "2026-12-31", "Valid": 1,
            "Username": "tzl9999", "FirstName": "Rocky", "LastName": "Balboa",
            "Email": "rocky@example.com",
            "AddressGPSLat": 50.0, "AddressGPSLon": 14.0,
            "Street": "Ulice 2", "City": "Praha", "Zip": "11000", "Country": "CZ",
            "Birthday": "1965-01-01", "Phone": "+420000000001", "Gender": "M",
            "PersNum": "650101/0000", "Nationality": "CZ",
            "SI": "980377", "SISport": 0, "SIType": 1,
            "SI2": "", "SISport2": 0, "SIType2": 0,
            "SI3": "", "SISport3": 0, "SIType3": 0,
            "IOFID": 0, "ShowFullCalendar": 0, "MyRegionsInCalendar": "",
            "DoNotReceiveEmailsFromORIS": 0, "NotifyAboutFeedbackByEmail": 0,
        },
    }
}


def _oris_response(endpoint, params=None, **kwargs):
    if endpoint == 'getClubUserList':
        return ORIS_CLUB_USER_LIST_RESPONSE_DATA
    return ORIS_REGISTER_USERS_RESPONSE_DATA


class ImportTestCase(TestCase):

    @mock.patch('orienteering_accounts.account.models.Account.add_to_google_workspace_group')
    @mock.patch('orienteering_accounts.account.models.Account.send_account_created_info_email')
    @mock.patch('orienteering_accounts.oris.client.ORISClient.make_get_request',
                side_effect=_oris_response)
    def test_import_accounts_from_oris(self, mock_get_registered_users, mock_email, mock_group):
        call_command('import_accounts_from_oris')
        mock_get_registered_users.assert_called()
        self.assertEqual(Account.objects.count(), 2)
```

`upsert_from_oris` copies the email from the club member and, when it differs,
calls Google Workspace; new accounts also send a welcome email. Both are patched
so the test exercises the import, not the notifications.

- [ ] **Step 5: Delete the stale account model test**

In `orienteering_accounts/account/tests/test_models.py`, delete the whole
`test_get_accounts_without_paid_club_membership` method. It calls
`Account.get_accounts_without_paid_club_membership(deadline)`, which no longer
exists. Its nearest replacement,
`Account.get_accounts_to_remove_entry_rights_in_oris()`, takes no deadline, reads
`is_late_with_club_membership_payment`, and yields rather than returning a
QuerySet — different enough that porting the assertions would mean designing new
coverage, which is not this plan's job.

Leave every other test in the file, and leave the imports alone unless deleting
the method makes one unused (`freeze_time`, `timedelta`); remove only ones that
are genuinely now unused.

- [ ] **Step 6: Stop two tests calling the live ORIS API**

`Entry.debt_init` -> `fee_after_club_discount` -> `Event.did_not_start` ->
`Event.results` issues a real `getEventResults` request. Two tests reach it.

In `orienteering_accounts/entry/tests/test_models.py`, in the
`EntryUpsertServicesOnlyFromOrisTestCase` class, add to `setUp` (create `setUp`
if the class has none, and call `super().setUp()` first if it does):

```python
        results_patcher = mock.patch.object(
            Event, 'results', new_callable=PropertyMock, return_value={}
        )
        results_patcher.start()
        self.addCleanup(results_patcher.stop)
```

Add whatever of `from unittest.mock import PropertyMock`, `import mock`, and
`from orienteering_accounts.event.models import Event` that file still needs.

In `orienteering_accounts/event/tests/test_update_entries.py`, add the same
patcher to the existing `setUp` in `UpdateEntriesTestCase`, next to the
`fee_patcher` already there. That file already imports `PropertyMock` and
`patch`; it needs `from orienteering_accounts.event.models import Event`.

An empty `results` dict makes `did_not_start()` return `True` for everyone,
which is what the unmocked call returned anyway for these fixtures — the point
is that no HTTP request leaves the test process.

- [ ] **Step 7: Run the full suite**

Run: `docker compose -f .superpowers/sdd/2026-09-22-oris-api-traffic-reduction/docker-compose.test.yml run --rm web python manage.py test orienteering_accounts`

Expected: `OK`, with 101 tests (103 minus the two deleted). If any test still
fails, report which and why rather than pressing on.

- [ ] **Step 8: Commit**

```bash
git add orienteering_accounts/event/tests orienteering_accounts/account/tests orienteering_accounts/entry/tests
git commit -m "test: Repair the failing test suite

Six tests failed on the committed code. test_import and test_refresh
called import_events_from_oris, a command that no longer exists; the
account import test fed the registration payload to getClubUserList too;
test_get_accounts_without_paid_club_membership covered a method that was
removed; and two tests reached Event.results, issuing live ORIS requests
from the suite. Point the event import test at Event.import_from_oris,
give the account test an endpoint-aware mock, mock Event.results, and
drop the two tests whose subjects no longer exist."
```

### Task 2: Cache the club roster

`get_club_member()` downloads the whole club roster to find one person and is
called once per account. This is ~40 000 of the ~60 000 daily requests.

**Files:**
- Modify: `orienteering_accounts/oris/client.py:216-243`
- Modify: `orienteering_accounts/settings/base.py`
- Create: `orienteering_accounts/oris/tests/fixtures.py`
- Test: `orienteering_accounts/oris/tests/test_client.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `ORISClient.get_club_members(club_key: int = settings.CLUB_KEY) -> typing.Dict[int, ClubMember]`
  - `ORISClient.invalidate_club_members_cache() -> None`
  - `ORISClient.get_club_member(user_id: int, club_key: int = settings.CLUB_KEY) -> typing.Optional[ClubMember]` — signature unchanged, so no caller changes.
  - `orienteering_accounts.oris.tests.fixtures.club_member_payload(...)` and `club_user_list_response(*members)`.

- [ ] **Step 1: Add the fixture builders**

`ClubMember` has 37 required fields, so hand-writing payloads in each test is
unworkable. Create `orienteering_accounts/oris/tests/fixtures.py`:

```python
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
```

- [ ] **Step 2: Write the failing tests**

Append to `orienteering_accounts/oris/tests/test_client.py`:

```python
class ClubMembersCacheTestCase(TestCase):

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.response_data = fixtures.club_user_list_response(
            fixtures.club_member_payload(390, 11, 'TZL6666', 'chuck@example.com'),
            fixtures.club_member_payload(377, 12, 'TZL9999', 'rocky@example.com'),
        )

    def test_roster_is_fetched_once_for_repeated_lookups(self):
        with mock.patch.object(ORISClient, 'make_get_request', return_value=self.response_data) as request_mock:
            first = ORISClient.get_club_member(390)
            second = ORISClient.get_club_member(377)

        self.assertEqual(request_mock.call_count, 1)
        self.assertEqual(first.email, 'chuck@example.com')
        self.assertEqual(second.email, 'rocky@example.com')

    def test_unknown_member_returns_none(self):
        with mock.patch.object(ORISClient, 'make_get_request', return_value=self.response_data):
            self.assertIsNone(ORISClient.get_club_member(999))

    def test_empty_response_is_not_cached(self):
        with mock.patch.object(ORISClient, 'make_get_request', return_value={}) as request_mock:
            ORISClient.get_club_member(390)
            ORISClient.get_club_member(390)

        self.assertEqual(request_mock.call_count, 2)

    def test_setting_entry_rights_invalidates_the_roster(self):
        with mock.patch.object(ORISClient, 'make_get_request', return_value=self.response_data) as request_mock:
            ORISClient.set_club_entry_rights(390, 11, can_entry_self=True)
            ORISClient.get_club_member(390)

        # roster, setClubEntryRights, roster again
        self.assertEqual(request_mock.call_count, 3)
```

Add these imports at the top of the file:

```python
from django.core.cache import cache

from orienteering_accounts.oris.tests import fixtures
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `docker compose -f .superpowers/sdd/2026-09-22-oris-api-traffic-reduction/docker-compose.test.yml run --rm web python manage.py test orienteering_accounts.oris.tests.test_client.ClubMembersCacheTestCase`
Expected: FAIL. `test_roster_is_fetched_once_for_repeated_lookups` fails with `AssertionError: 2 != 1`.

- [ ] **Step 4: Add the settings**

In `orienteering_accounts/settings/base.py`, next to the existing `ORIS_*` block:

```python
ORIS_CLUB_USER_LIST_CACHE_KEY = 'oris_club_user_list'
ORIS_CLUB_USER_LIST_CACHE_TIMEOUT = 60 * 60
```

- [ ] **Step 5: Implement the cache**

Add `from django.core.cache import cache` to the imports in
`orienteering_accounts/oris/client.py`, then replace the existing
`get_club_member` classmethod with:

```python
    @classmethod
    def get_club_members(cls, club_key: int = settings.CLUB_KEY) -> typing.Dict[int, ClubMember]:
        response_data = cache.get(settings.ORIS_CLUB_USER_LIST_CACHE_KEY)

        if response_data is None:
            response_data = cls.make_get_request('getClubUserList', params={'clubkey': club_key})

            if response_data:
                # An empty payload means ORIS hiccupped; caching it would starve
                # every caller for a full hour.
                cache.set(
                    settings.ORIS_CLUB_USER_LIST_CACHE_KEY,
                    response_data,
                    settings.ORIS_CLUB_USER_LIST_CACHE_TIMEOUT,
                )

        club_members = {}

        for _, club_user_dict in (response_data or {}).get('ClubMembers', {}).items():
            club_member = ClubMember(**club_user_dict)
            club_members[club_member.user_id] = club_member

        return club_members

    @classmethod
    def invalidate_club_members_cache(cls):
        cache.delete(settings.ORIS_CLUB_USER_LIST_CACHE_KEY)

    @classmethod
    def get_club_member(cls, user_id: int, club_key: int = settings.CLUB_KEY) -> typing.Optional[ClubMember]:
        return cls.get_club_members(club_key=club_key).get(int(user_id))
```

The old code compared `club_user_dict['UserID'] == str(user_id)`; keying the
dict by the pydantic-coerced `int` and looking up `int(user_id)` is equivalent.

- [ ] **Step 6: Invalidate on write**

In `set_club_entry_rights`, replace the final `return cls.make_get_request(...)` line with:

```python
        response = cls.make_get_request('setClubEntryRights', params=params)

        # AllowEntrySelf just changed, so the cached roster is stale.
        cls.invalidate_club_members_cache()

        return response
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `docker compose -f .superpowers/sdd/2026-09-22-oris-api-traffic-reduction/docker-compose.test.yml run --rm web python manage.py test orienteering_accounts.oris.tests.test_client`
Expected: PASS, including the existing retry tests.

- [ ] **Step 8: Run the full suite**

Run: `docker compose -f .superpowers/sdd/2026-09-22-oris-api-traffic-reduction/docker-compose.test.yml run --rm web python manage.py test orienteering_accounts`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add orienteering_accounts/oris/client.py orienteering_accounts/oris/tests orienteering_accounts/settings/base.py
git commit -m "perf(oris): Cache the club roster instead of refetching it per member

get_club_member downloaded the entire getClubUserList payload to find
one person, once per account. That was ~40k of the ~60k daily requests
the ORIS maintainer reported. Fetch the roster once per hour and look
members up in memory; invalidate on setClubEntryRights."
```

---

### Task 3: Cache registrations and stop the bank job polling ORIS while idle

`process_bank_transactions` runs every minute and fetches ORIS registrations
before checking whether the bank returned anything. That is ~2 880 wasted
requests a day.

**Files:**
- Modify: `orienteering_accounts/oris/client.py:94-125`
- Modify: `orienteering_accounts/account/services.py:28-30`
- Modify: `orienteering_accounts/settings/base.py`
- Test: `orienteering_accounts/account/tests/test_process_bank_transaction.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `ORISClient.get_registered_users(...)` keeps its signature and return type `typing.List[RegisteredUser]`; it now reads through a per-`(sport, year)` cache.

- [ ] **Step 1: Write the failing test**

Append to `orienteering_accounts/account/tests/test_process_bank_transaction.py`:

```python
class IdleBankRunTestCase(TestCase):

    def test_no_bank_transactions_means_no_oris_request(self):
        with mock.patch('orienteering_accounts.oris.client.ORISClient.make_get_request') as request_mock:
            process_bank_transactions_batch([], None)

        request_mock.assert_not_called()
```

Add the import the test needs:

```python
from orienteering_accounts.account.services import process_bank_transactions_batch
```

(If `mock` and `TestCase` are not already imported in that file, add
`from unittest import mock` and `from django.test import TestCase`.)

- [ ] **Step 2: Run the test to verify it fails**

Run: `docker compose -f .superpowers/sdd/2026-09-22-oris-api-traffic-reduction/docker-compose.test.yml run --rm web python manage.py test orienteering_accounts.account.tests.test_process_bank_transaction.IdleBankRunTestCase`
Expected: FAIL with `Expected 'make_get_request' to not have been called. Called 2 times.`

- [ ] **Step 3: Return early when there is nothing to process**

In `orienteering_accounts/account/services.py`, change the opening of
`process_bank_transactions_batch`:

```python
def process_bank_transactions_batch(bank_transactions, payment_period):
    """Process a batch of bank transactions. Each transaction in try/except."""
    if not bank_transactions:
        return

    oris_registered_numbers = _get_oris_registered_numbers()
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `docker compose -f .superpowers/sdd/2026-09-22-oris-api-traffic-reduction/docker-compose.test.yml run --rm web python manage.py test orienteering_accounts.account.tests.test_process_bank_transaction.IdleBankRunTestCase`
Expected: PASS.

- [ ] **Step 5: Add the registration cache settings**

In `orienteering_accounts/settings/base.py`:

```python
ORIS_REGISTRATIONS_CACHE_KEY_PATTERN = 'oris_registrations:{sport}:{year}'
ORIS_REGISTRATIONS_CACHE_TIMEOUT = 60 * 60
```

- [ ] **Step 6: Write the failing cache test**

Append to `orienteering_accounts/oris/tests/test_client.py`:

```python
class RegisteredUsersCacheTestCase(TestCase):

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.response_data = {
            'Reg_1': {
                'RegNo': 'TZL6666', 'UserID': '390', 'Lic': 'C', 'FirstName': 'Chuck',
                'LastName': 'Norris', 'SI': '7207026', 'Paid': '1', 'ClubID': 1,
                'Gender': 'M', 'Born': '70', 'Fee': '60',
            },
        }

    def test_registrations_are_fetched_once_per_sport_and_year(self):
        with mock.patch.object(ORISClient, 'make_get_request', return_value=self.response_data) as request_mock:
            ORISClient.get_registered_users(year=2026, sport=1)
            ORISClient.get_registered_users(year=2026, sport=1, licence='C')

        self.assertEqual(request_mock.call_count, 1)

    def test_different_sport_is_fetched_separately(self):
        with mock.patch.object(ORISClient, 'make_get_request', return_value=self.response_data) as request_mock:
            ORISClient.get_registered_users(year=2026, sport=1)
            ORISClient.get_registered_users(year=2026, sport=3)

        self.assertEqual(request_mock.call_count, 2)
```

- [ ] **Step 7: Run it to verify it fails**

Run: `docker compose -f .superpowers/sdd/2026-09-22-oris-api-traffic-reduction/docker-compose.test.yml run --rm web python manage.py test orienteering_accounts.oris.tests.test_client.RegisteredUsersCacheTestCase`
Expected: FAIL with `AssertionError: 2 != 1`.

- [ ] **Step 8: Implement the cache**

In `orienteering_accounts/oris/client.py`, replace the first five lines of the
body of `get_registered_users` (the `params` dict and the `make_get_request`
call) with:

```python
        year = year or datetime.now().year
        cache_key = settings.ORIS_REGISTRATIONS_CACHE_KEY_PATTERN.format(sport=sport, year=year)
        response_data = cache.get(cache_key)

        if response_data is None:
            response_data = cls.make_get_request('getRegistration', params={'year': year, 'sport': sport})

            if response_data:
                cache.set(cache_key, response_data, settings.ORIS_REGISTRATIONS_CACHE_TIMEOUT)
```

Leave the rest of the method — the `licence` and `club_id` filtering loop —
exactly as it is. Filtering stays in Python because the endpoint takes no such
parameters.

- [ ] **Step 9: Run the tests to verify they pass**

Run: `docker compose -f .superpowers/sdd/2026-09-22-oris-api-traffic-reduction/docker-compose.test.yml run --rm web python manage.py test orienteering_accounts.oris orienteering_accounts.account`
Expected: PASS.

- [ ] **Step 10: Run the full suite and commit**

Run: `docker compose -f .superpowers/sdd/2026-09-22-oris-api-traffic-reduction/docker-compose.test.yml run --rm web python manage.py test orienteering_accounts`
Expected: PASS.

```bash
git add orienteering_accounts/oris orienteering_accounts/account/services.py orienteering_accounts/account/tests orienteering_accounts/settings/base.py
git commit -m "perf(oris): Cache registrations and skip ORIS on idle bank runs

process_bank_transactions runs every minute and fetched the full CSOS
registration list before checking whether the bank returned anything,
costing ~2.9k requests a day for nothing. Return early when the batch is
empty and read registrations through a one-hour cache."
```

---

### Task 4: Set ORIS entry rights only on an actual threshold crossing

`check_balance()` calls `add_entry_rights_in_oris()` on every transaction save
whose balance sits above the threshold, not only when the threshold is crossed.
Each call costs two ORIS requests. `docs/transaction_flow.md` documents the
intended behaviour (branch H -> I), so the code contradicts its own docs.

**Files:**
- Modify: `orienteering_accounts/account/signals.py:64-95`
- Test: `orienteering_accounts/account/tests/test_entry_rights_signal.py` (create)

**Interfaces:**
- Consumes: nothing.
- Produces: no API change. `check_balance(account, old_balance)` keeps its signature.

- [ ] **Step 1: Write the failing tests**

The signal work runs in `transaction.on_commit`, so the tests must use
`captureOnCommitCallbacks(execute=True)` or nothing will fire. Create
`orienteering_accounts/account/tests/test_entry_rights_signal.py`:

```python
from decimal import Decimal
from unittest import mock

from django.conf import settings
from django.test import TestCase
from model_bakery import baker

from orienteering_accounts.account.models import Transaction


class EntryRightsSignalTestCase(TestCase):

    def setUp(self):
        for target in [
            'orienteering_accounts.account.models.Account.send_debts_payment_info_email',
            'orienteering_accounts.account.models.Account.send_entry_rights_removed_info_email',
            'orienteering_accounts.account.models.Account.send_entry_rights_restored_info_email',
        ]:
            patcher = mock.patch(target)
            patcher.start()
            self.addCleanup(patcher.stop)

        add_patcher = mock.patch('orienteering_accounts.account.models.Account.add_entry_rights_in_oris')
        self.add_rights_mock = add_patcher.start()
        self.addCleanup(add_patcher.stop)

        remove_patcher = mock.patch('orienteering_accounts.account.models.Account.remove_entry_rights_in_oris')
        self.remove_rights_mock = remove_patcher.start()
        self.addCleanup(remove_patcher.stop)

        self.threshold = Decimal(str(settings.MAXIMUM_NEGATIVE_BALANCE))
        self.account = baker.make('account.Account', init_balance=Decimal('0'), oris_club_member_id=11)

    def _add_transaction(self, amount):
        with self.captureOnCommitCallbacks(execute=True):
            return baker.make(
                Transaction,
                account=self.account,
                amount=amount,
                purpose=Transaction.TransactionPurpose.ENTRY,
            )

    def test_transaction_above_threshold_does_not_touch_oris(self):
        self._add_transaction(Decimal('-100'))

        self.add_rights_mock.assert_not_called()
        self.remove_rights_mock.assert_not_called()

    def test_crossing_threshold_downwards_removes_rights_once(self):
        self._add_transaction(self.threshold - Decimal('100'))

        self.remove_rights_mock.assert_called_once()
        self.add_rights_mock.assert_not_called()

    def test_crossing_threshold_upwards_restores_rights_once(self):
        self._add_transaction(self.threshold - Decimal('100'))
        self.remove_rights_mock.reset_mock()

        self._add_transaction(Decimal('5000'))

        self.add_rights_mock.assert_called_once()

    def test_deleting_a_transaction_without_crossing_does_not_touch_oris(self):
        created = self._add_transaction(Decimal('-100'))
        self.add_rights_mock.reset_mock()

        with self.captureOnCommitCallbacks(execute=True):
            created.delete()

        self.add_rights_mock.assert_not_called()
        self.remove_rights_mock.assert_not_called()
```

- [ ] **Step 2: Run the tests to verify the right ones fail**

Run: `docker compose -f .superpowers/sdd/2026-09-22-oris-api-traffic-reduction/docker-compose.test.yml run --rm web python manage.py test orienteering_accounts.account.tests.test_entry_rights_signal`
Expected: `test_transaction_above_threshold_does_not_touch_oris` and
`test_deleting_a_transaction_without_crossing_does_not_touch_oris` FAIL with
`Expected 'add_entry_rights_in_oris' to not have been called`. The two crossing
tests should already PASS — they describe behaviour that must be preserved.

- [ ] **Step 3: Move the call inside the crossing branch**

In `orienteering_accounts/account/signals.py`, delete the bare
`account.add_entry_rights_in_oris()` line that sits directly under
`if balance > maximum_threshold:`, and add it as the first statement inside the
`try:` of the `if old_balance <= maximum_threshold:` branch, immediately above
the existing `logger.info(...)` call:

```python
    if balance > maximum_threshold:
        if old_balance <= maximum_threshold:
            # Balance was previously at or below max threshold, add back entry rights
            try:
                account.add_entry_rights_in_oris()
                logger.info(
                    f'ORIS entry rights restored for {account.full_name} '
                    f'({account.registration_number}). Balance: {balance}'
                )
```

Change nothing else in the function. Do not reindent or reflow the rest of the
branch, and leave existing trailing whitespace alone.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `docker compose -f .superpowers/sdd/2026-09-22-oris-api-traffic-reduction/docker-compose.test.yml run --rm web python manage.py test orienteering_accounts.account.tests.test_entry_rights_signal`
Expected: PASS, all four.

- [ ] **Step 5: Run the full suite**

Run: `docker compose -f .superpowers/sdd/2026-09-22-oris-api-traffic-reduction/docker-compose.test.yml run --rm web python manage.py test orienteering_accounts`
Expected: PASS. `event/tests/test_update_entries.py` patches both entry-rights
methods already, so it is unaffected.

- [ ] **Step 6: Commit**

```bash
git add orienteering_accounts/account/signals.py orienteering_accounts/account/tests/test_entry_rights_signal.py
git commit -m "fix(account): Set ORIS entry rights only when the threshold is crossed

check_balance called add_entry_rights_in_oris on every transaction save
with a balance above the threshold, costing two ORIS requests each time
and firing again for every future transaction deleted by
Event.update_entries. docs/transaction_flow.md already specifies that
rights are restored only when the balance recovers; make the code match."
```

---

### Task 5: Cap and count ORIS requests in the client

Nothing structural stops a future bug from producing another 60 000-request
day. The client only has a 429 retry, which makes a rate-limited situation
worse by waiting and pushing on.

**Files:**
- Modify: `orienteering_accounts/oris/client.py:60-80`
- Modify: `orienteering_accounts/settings/base.py`
- Modify: `orienteering_accounts/event/management/commands/process_events.py`
- Modify: `orienteering_accounts/account/management/commands/import_accounts_from_oris.py`
- Test: `orienteering_accounts/oris/tests/test_client.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `orienteering_accounts.oris.client.ORISRateLimitExceeded(Exception)`
  - `ORISClient.log_request_stats() -> None`
  - `ORISClient.reset_request_stats() -> None`

- [ ] **Step 1: Add the settings**

In `orienteering_accounts/settings/base.py`:

```python
ORIS_API_MAX_REQUESTS_PER_MINUTE = 60
ORIS_API_DAILY_REQUEST_BUDGET = 5000
```

- [ ] **Step 2: Write the failing tests**

Append to `orienteering_accounts/oris/tests/test_client.py`:

```python
class RequestBudgetTestCase(TestCase):

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        ORISClient.reset_request_stats()
        self.addCleanup(ORISClient.reset_request_stats)

    @override_settings(ORIS_API_DAILY_REQUEST_BUDGET=2)
    def test_exhausting_the_daily_budget_raises(self):
        with mock.patch('orienteering_accounts.oris.client.requests.get', return_value=_response(200)):
            ORISClient.make_get_request('getVersion')
            ORISClient.make_get_request('getVersion')

            with self.assertRaises(oris_client.ORISRateLimitExceeded):
                ORISClient.make_get_request('getVersion')

    @override_settings(ORIS_API_MAX_REQUESTS_PER_MINUTE=1)
    def test_exceeding_the_per_minute_cap_sleeps_instead_of_failing(self):
        with mock.patch('orienteering_accounts.oris.client.time.sleep') as sleep_mock:
            with mock.patch('orienteering_accounts.oris.client.requests.get', return_value=_response(200)):
                ORISClient.make_get_request('getVersion')
                ORISClient.make_get_request('getVersion')

        sleep_mock.assert_called_once()

    def test_requests_are_counted_per_method(self):
        with mock.patch('orienteering_accounts.oris.client.requests.get', return_value=_response(200)):
            ORISClient.make_get_request('getEventList')
            ORISClient.make_get_request('getEventList')
            ORISClient.make_get_request('getEvent')

        self.assertEqual(ORISClient.request_counter['getEventList'], 2)
        self.assertEqual(ORISClient.request_counter['getEvent'], 1)
```

Add `from django.test import override_settings` to the imports.

- [ ] **Step 3: Run them to verify they fail**

Run: `docker compose -f .superpowers/sdd/2026-09-22-oris-api-traffic-reduction/docker-compose.test.yml run --rm web python manage.py test orienteering_accounts.oris.tests.test_client.RequestBudgetTestCase`
Expected: FAIL with `AttributeError: type object 'ORISClient' has no attribute 'reset_request_stats'`.

- [ ] **Step 4: Implement the cap and the counters**

In `orienteering_accounts/oris/client.py`, add `from collections import Counter`
to the imports (there is already a `from collections import defaultdict`; extend
it to `from collections import Counter, defaultdict`), add
`from django.utils import timezone`, and define the exception next to the
existing module constants:

```python
class ORISRateLimitExceeded(Exception):
    """Raised when the configured daily ORIS request budget is exhausted."""
```

Then add these classmethods to `ORISClient`, above `make_request`:

```python
    request_counter = Counter()

    @classmethod
    def reset_request_stats(cls):
        cls.request_counter = Counter()

    @classmethod
    def log_request_stats(cls):
        if not cls.request_counter:
            return

        breakdown = ', '.join(
            f'{endpoint}={count}' for endpoint, count in sorted(cls.request_counter.items())
        )
        logger.info(f'ORIS API requests this run: {sum(cls.request_counter.values())} ({breakdown})')

    @classmethod
    def _incr(cls, key: str, timeout: int) -> int:
        cache.add(key, 0, timeout)

        try:
            return cache.incr(key)
        except ValueError:
            # The key expired between add() and incr(); start the window again.
            cache.set(key, 1, timeout)
            return 1

    @classmethod
    def _consume_request_budget(cls, endpoint: str):
        now = timezone.now()

        daily_count = cls._incr(f'oris_api_requests:{now:%Y%m%d}', 60 * 60 * 26)

        if daily_count > settings.ORIS_API_DAILY_REQUEST_BUDGET:
            raise ORISRateLimitExceeded(
                f'Daily ORIS request budget of {settings.ORIS_API_DAILY_REQUEST_BUDGET} '
                f'is exhausted ({daily_count} requests today).'
            )

        minute_count = cls._incr(f'oris_api_requests:{now:%Y%m%d%H%M}', 120)

        if minute_count > settings.ORIS_API_MAX_REQUESTS_PER_MINUTE:
            delay = 60 - now.second
            logger.warning(f'ORIS API per-minute cap reached, waiting {delay} s.')
            time.sleep(delay)

        cls.request_counter[endpoint] += 1
```

Then call it as the first statement in `make_request`:

```python
    @classmethod
    def make_request(cls, method: str, endpoint: str, params: dict = None, data: dict = None, **kwargs):
        cls._consume_request_budget(endpoint)

        default_params = {
```

`get_ranking` bypasses `make_request` because it downloads a CSV export from a
different URL. Leave it alone; it is six requests a day.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `docker compose -f .superpowers/sdd/2026-09-22-oris-api-traffic-reduction/docker-compose.test.yml run --rm web python manage.py test orienteering_accounts.oris.tests.test_client`
Expected: PASS. The existing retry tests call `make_get_request` too, so they
now consume budget; with the default of 5000 that is irrelevant.

- [ ] **Step 6: Log the stats at the end of the two busiest commands**

In `orienteering_accounts/event/management/commands/process_events.py`, add the
import `from orienteering_accounts.oris.client import ORISClient` and, as the
last statement of `handle`:

```python
        ORISClient.log_request_stats()
```

Do the same in
`orienteering_accounts/account/management/commands/import_accounts_from_oris.py`
(which already imports `ORISClient`), as the last statement of `handle`.

- [ ] **Step 7: Run the full suite and commit**

Run: `docker compose -f .superpowers/sdd/2026-09-22-oris-api-traffic-reduction/docker-compose.test.yml run --rm web python manage.py test orienteering_accounts`
Expected: PASS.

```bash
git add orienteering_accounts/oris orienteering_accounts/settings/base.py orienteering_accounts/event/management/commands/process_events.py orienteering_accounts/account/management/commands/import_accounts_from_oris.py
git commit -m "feat(oris): Cap and count ORIS API requests

Add a Redis-backed per-minute cap and a daily budget to the client, so a
future regression cannot quietly produce another 60k-request day, plus a
per-method request counter logged at the end of each run. Exhausting the
daily budget raises, which surfaces through the cron heartbeats rather
than silently serving stale data."
```

---

### Task 6: Store the club entry markers that `getEventList` returns

`getEventList` with `myClubId` returns `ClubEntryCount`,
`ClubEntryLastModifiedTimeStamp`, `ClubServiceEntryCount` and
`ClubServiceEntryLastModifiedTimeStamp`. Nothing reads them today. Task 8 needs
them persisted so it can compare runs.

**Files:**
- Modify: `orienteering_accounts/oris/models.py:90-123`
- Modify: `orienteering_accounts/event/models.py:35-70`, `:118-125`
- Create: `orienteering_accounts/event/migrations/0014_event_club_entry_markers.py`
- Modify: `orienteering_accounts/event/tests/fixtures.py`
- Test: `orienteering_accounts/event/tests/test_club_markers.py` (create)

**Interfaces:**
- Consumes: nothing.
- Produces: `event.Event` gains `oris_club_entry_count: int`,
  `oris_club_entry_last_modified_timestamp: Optional[int]`,
  `oris_club_service_entry_count: int`,
  `oris_club_service_entry_last_modified_timestamp: Optional[int]` and
  `entries_synced_at: Optional[datetime]`. The pydantic
  `oris.models.Event` gains the same four names (not the timestamp), because
  `Event.upsert_from_oris()` passes `event.dict()` straight into `defaults=`.

- [ ] **Step 1: Write the failing test**

Create `orienteering_accounts/event/tests/test_club_markers.py`:

```python
from unittest import mock

from django.test import TestCase

from orienteering_accounts.event.models import Event
from orienteering_accounts.event.tests import fixtures
from orienteering_accounts.oris.models import Event as OrisEvent


class ClubMarkersTestCase(TestCase):

    def test_list_payload_populates_club_markers(self):
        payload = list(fixtures.ORIS_EVENTS_RESPONSE_DATA.values())[0]

        event = Event.upsert_from_oris(OrisEvent(**payload))

        self.assertEqual(event.oris_club_entry_count, 3)
        self.assertEqual(event.oris_club_entry_last_modified_timestamp, 1769371100)
        self.assertEqual(event.oris_club_service_entry_count, 1)
        self.assertEqual(event.oris_club_service_entry_last_modified_timestamp, 1769371200)

    def test_detail_refresh_does_not_wipe_club_markers(self):
        list_payload = list(fixtures.ORIS_EVENTS_RESPONSE_DATA.values())[0]
        event = Event.upsert_from_oris(OrisEvent(**list_payload))

        with mock.patch('orienteering_accounts.oris.client.ORISClient.make_get_request',
                        return_value=fixtures.ORIS_EVENT_RESPONSE_DATA):
            event._refresh_from_oris()

        event.refresh_from_db()
        self.assertEqual(event.oris_club_entry_count, 3)
        self.assertEqual(event.oris_club_entry_last_modified_timestamp, 1769371100)
```

The second test is the important one. `getEvent` never returns the club fields,
so a detail refresh writing `event.dict()` would overwrite them with defaults
and make every run look like "entries changed".

- [ ] **Step 2: Add the markers to the fixture**

In `orienteering_accounts/event/tests/fixtures.py`, add these four keys to the
`"Event_5712"` dict inside `ORIS_EVENTS_RESPONSE_DATA`, next to the existing
`"ServicesLastModifiedTimeStamp": 0,` line:

```python
        "ClubEntryCount": "3",
        "ClubEntryLastModifiedTimeStamp": 1769371100,
        "ClubServiceEntryCount": "1",
        "ClubServiceEntryLastModifiedTimeStamp": 1769371200,
```

Leave `ORIS_EVENT_RESPONSE_DATA` (the `getEvent` detail payload) untouched —
its lack of these keys is exactly what the second test exercises. The counts are
strings because that is how ORIS returns them; pydantic coerces them.

- [ ] **Step 3: Run the test to verify it fails**

Run: `docker compose -f .superpowers/sdd/2026-09-22-oris-api-traffic-reduction/docker-compose.test.yml run --rm web python manage.py test orienteering_accounts.event.tests.test_club_markers`
Expected: FAIL with `AttributeError: 'Event' object has no attribute 'oris_club_entry_count'`.

- [ ] **Step 4: Add the pydantic fields**

In `orienteering_accounts/oris/models.py`, inside `class Event`, next to
`oris_services_last_modified_timestamp`:

```python
    oris_club_entry_count: typing.Optional[int] = Field(alias='ClubEntryCount')
    oris_club_entry_last_modified_timestamp: typing.Optional[int] = Field(alias='ClubEntryLastModifiedTimeStamp')
    oris_club_service_entry_count: typing.Optional[int] = Field(alias='ClubServiceEntryCount')
    oris_club_service_entry_last_modified_timestamp: typing.Optional[int] = Field(alias='ClubServiceEntryLastModifiedTimeStamp')
```

The names deliberately match the Django field names, because
`upsert_from_oris` feeds `event.dict()` into `defaults=`.

- [ ] **Step 5: Add the Django fields**

In `orienteering_accounts/event/models.py`, in `class Event`, after
`oris_services_last_modified_timestamp`:

```python
    oris_club_entry_count = models.PositiveIntegerField(default=0)
    oris_club_entry_last_modified_timestamp = models.PositiveIntegerField(null=True, blank=True)
    oris_club_service_entry_count = models.PositiveIntegerField(default=0)
    oris_club_service_entry_last_modified_timestamp = models.PositiveIntegerField(null=True, blank=True)
```

and, in the `### Internals` block after `bills_solved_at`:

```python
    entries_synced_at = models.DateTimeField(null=True, blank=True)
```

- [ ] **Step 6: Close the overwrite trap**

In `orienteering_accounts/event/models.py`, change `upsert_from_oris` to skip
fields the payload did not contain:

```python
    @classmethod
    def upsert_from_oris(cls, event):
        instance, _ = cls.objects.update_or_create(
            oris_id=event.oris_id,
            defaults=event.dict(exclude_unset=True)
        )
        instance.refresh_from_db()
        return instance
```

`exclude_unset=True` is already the idiom used on the update path in
`import_from_oris`. Every field the Django model requires is present in both the
list and the detail payloads, so creates still work.

- [ ] **Step 7: Generate the migration**

Run: `docker compose run --rm web python manage.py makemigrations event --name club_entry_markers`
Expected: creates `orienteering_accounts/event/migrations/0014_club_entry_markers.py` adding five fields. Read it and confirm it contains exactly those five `AddField` operations and nothing else.

- [ ] **Step 8: Run the tests to verify they pass**

Run: `docker compose -f .superpowers/sdd/2026-09-22-oris-api-traffic-reduction/docker-compose.test.yml run --rm web python manage.py test orienteering_accounts.event.tests.test_club_markers`
Expected: PASS.

- [ ] **Step 9: Run the full suite and commit**

Run: `docker compose -f .superpowers/sdd/2026-09-22-oris-api-traffic-reduction/docker-compose.test.yml run --rm web python manage.py test orienteering_accounts`
Expected: PASS.

```bash
git add orienteering_accounts/oris/models.py orienteering_accounts/event/models.py orienteering_accounts/event/migrations orienteering_accounts/event/tests
git commit -m "feat(event): Persist the club entry markers from getEventList

getEventList returns per-event change markers for our own club when
called with myClubId; store them so the sync can tell what actually
changed. upsert_from_oris now writes only the fields the payload
contained, so a getEvent detail refresh no longer wipes them."
```

---

### Task 7: Let `get_events` request a window and the club markers

**Files:**
- Modify: `orienteering_accounts/oris/client.py:127-143`
- Test: `orienteering_accounts/oris/tests/test_client.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `ORISClient.get_events(sport: int = oris_choices.SPORT_OB, include_unofficial_events=0, date_from: typing.Optional[date] = None, date_to: typing.Optional[date] = None, my_club_id: typing.Optional[int] = None) -> typing.List[Event]`. Existing callers that pass only `sport` and `include_unofficial_events` keep working.

- [ ] **Step 1: Write the failing test**

Append to `orienteering_accounts/oris/tests/test_client.py`:

```python
class EventListParamsTestCase(TestCase):

    def test_window_and_club_id_are_sent(self):
        with mock.patch.object(ORISClient, 'make_get_request', return_value={}) as request_mock:
            ORISClient.get_events(
                sport=1,
                include_unofficial_events=1,
                date_from=date(2026, 9, 8),
                date_to=date(2027, 1, 20),
                my_club_id=204,
            )

        request_mock.assert_called_once_with('getEventList', params={
            'sport': 1,
            'all': 1,
            'datefrom': '2026-09-08',
            'dateto': '2027-01-20',
            'myClubId': 204,
        })

    def test_optional_params_are_omitted(self):
        with mock.patch.object(ORISClient, 'make_get_request', return_value={}) as request_mock:
            ORISClient.get_events(sport=1)

        request_mock.assert_called_once_with('getEventList', params={'sport': 1, 'all': 0})
```

Add `from datetime import date` to the test imports.

- [ ] **Step 2: Run it to verify it fails**

Run: `docker compose -f .superpowers/sdd/2026-09-22-oris-api-traffic-reduction/docker-compose.test.yml run --rm web python manage.py test orienteering_accounts.oris.tests.test_client.EventListParamsTestCase`
Expected: FAIL with `TypeError: get_events() got an unexpected keyword argument 'date_from'`.

- [ ] **Step 3: Implement the parameters**

In `orienteering_accounts/oris/client.py`, replace the signature and the
`params` construction of `get_events`:

```python
    @classmethod
    def get_events(
        cls,
        sport: int = oris_choices.SPORT_OB,
        include_unofficial_events=0,
        date_from: typing.Optional[date] = None,
        date_to: typing.Optional[date] = None,
        my_club_id: typing.Optional[int] = None,
    ) -> typing.List[Event]:
        params = {
            'sport': sport,
            'all': include_unofficial_events
        }

        if date_from:
            params['datefrom'] = date_from.isoformat()

        if date_to:
            params['dateto'] = date_to.isoformat()

        if my_club_id:
            params['myClubId'] = my_club_id

        response_data = cls.make_get_request('getEventList', params=params)
```

Leave the loop that builds the `events` list untouched. `date` is already
imported at the top of the module.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `docker compose -f .superpowers/sdd/2026-09-22-oris-api-traffic-reduction/docker-compose.test.yml run --rm web python manage.py test orienteering_accounts.oris.tests.test_client`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add orienteering_accounts/oris
git commit -m "feat(oris): Support date window and myClubId in get_events

getEventList accepts datefrom, dateto and myClubId; the last one makes
the response carry per-event club entry markers. Needed by the
change-driven event sync."
```

---

### Task 8: Drive the event sync from change markers

This is the core of the plan. Today `import_from_oris` fetches the whole
remaining calendar for three sports and spends three to four requests on every
future event, every five minutes.

**Files:**
- Modify: `orienteering_accounts/event/models.py:94-135`, `:323-333`
- Modify: `orienteering_accounts/oris/client.py:167-176` (delete `club_entry_exists`)
- Modify: `orienteering_accounts/settings/base.py`
- Test: `orienteering_accounts/event/tests/test_change_detection.py` (create)

**Interfaces:**
- Consumes: `ORISClient.get_events(..., date_from, date_to, my_club_id)` from Task 7; the five model fields from Task 6.
- Produces:
  - `Event.import_from_oris()` — unchanged signature, new behaviour.
  - `Event._sync_from_oris_list_item(event: OrisEvent, today: date) -> None`
  - `Event.refresh_from_oris()` and `ORISClient.club_entry_exists()` are **deleted**.

- [ ] **Step 1: Add the window setting**

In `orienteering_accounts/settings/base.py`, next to the existing
`REFRESH_EVENTS_BEFORE_DAYS = 14`:

```python
ORIS_EVENT_LIST_WINDOW_DAYS_AHEAD = 120
```

- [ ] **Step 2: Write the failing tests**

Create `orienteering_accounts/event/tests/test_change_detection.py`:

```python
import copy
from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from orienteering_accounts.event.models import Event
from orienteering_accounts.event.tests import fixtures
from orienteering_accounts.oris import choices as oris_choices
from orienteering_accounts.oris.models import Event as OrisEvent


def _future_list_payload(**overrides):
    payload = copy.deepcopy(list(fixtures.ORIS_EVENTS_RESPONSE_DATA.values())[0])
    payload['Date'] = (timezone.now().date() + timedelta(days=7)).isoformat()
    payload.update(overrides)
    return {'Event_5712': payload}


class ChangeDetectionTestCase(TestCase):

    def setUp(self):
        entries_patcher = mock.patch('orienteering_accounts.event.models.Event.update_entries')
        self.update_entries_mock = entries_patcher.start()
        self.addCleanup(entries_patcher.stop)

        refresh_patcher = mock.patch('orienteering_accounts.event.models.Event._refresh_from_oris')
        self.refresh_from_oris_mock = refresh_patcher.start()
        self.addCleanup(refresh_patcher.stop)

        rate_patcher = mock.patch('orienteering_accounts.event.models.Event._update_exchange_rate')
        self.update_exchange_rate_mock = rate_patcher.start()
        self.addCleanup(rate_patcher.stop)

    def _import(self, payload):
        def fake_get_events(**kwargs):
            if kwargs['sport'] != oris_choices.SPORT_OB:
                return []
            return [OrisEvent(**item) for item in payload.values()]

        with mock.patch('orienteering_accounts.oris.client.ORISClient.get_events', side_effect=fake_get_events):
            Event.import_from_oris()

    def test_first_import_fetches_detail_and_entries(self):
        self._import(_future_list_payload())

        self.refresh_from_oris_mock.assert_called_once()
        self.update_entries_mock.assert_called_once()

    def test_unchanged_event_fetches_nothing(self):
        payload = _future_list_payload()
        self._import(payload)
        self.refresh_from_oris_mock.reset_mock()
        self.update_entries_mock.reset_mock()

        self._import(payload)

        self.refresh_from_oris_mock.assert_not_called()
        self.update_entries_mock.assert_not_called()

    def test_bumped_version_fetches_detail_only(self):
        self._import(_future_list_payload())
        self.refresh_from_oris_mock.reset_mock()
        self.update_entries_mock.reset_mock()

        self._import(_future_list_payload(Version='15'))

        self.refresh_from_oris_mock.assert_called_once()
        self.update_entries_mock.assert_not_called()

    def test_bumped_entry_timestamp_fetches_entries_only(self):
        self._import(_future_list_payload())
        self.refresh_from_oris_mock.reset_mock()
        self.update_entries_mock.reset_mock()

        self._import(_future_list_payload(ClubEntryLastModifiedTimeStamp=1769999999))

        self.update_entries_mock.assert_called_once()
        self.refresh_from_oris_mock.assert_not_called()

    def test_changed_entry_count_with_unchanged_timestamp_is_detected(self):
        self._import(_future_list_payload())
        self.update_entries_mock.reset_mock()

        self._import(_future_list_payload(ClubEntryCount='4'))

        self.update_entries_mock.assert_called_once()

    def test_changed_service_count_fetches_entries(self):
        self._import(_future_list_payload())
        self.update_entries_mock.reset_mock()

        self._import(_future_list_payload(ClubServiceEntryCount='2'))

        self.update_entries_mock.assert_called_once()

    def test_past_event_is_not_entry_synced(self):
        payload = copy.deepcopy(list(fixtures.ORIS_EVENTS_RESPONSE_DATA.values())[0])
        payload['Date'] = (timezone.now().date() - timedelta(days=3)).isoformat()

        self._import({'Event_5712': payload})

        self.refresh_from_oris_mock.assert_called_once()
        self.update_entries_mock.assert_not_called()


class RelayHandledTestCase(TestCase):

    def test_relay_handled_check_makes_no_oris_request(self):
        from django.conf import settings
        from model_bakery import baker

        event = baker.make(
            'event.Event',
            discipline={'oris_id': settings.ORIS_RELAY_RACE_IDS[0]},
            oris_club_entry_count=2,
            handled=False,
            handled_disabled=False,
        )

        with mock.patch('orienteering_accounts.oris.client.ORISClient.make_get_request') as request_mock:
            self.assertTrue(event.should_be_handled())

        request_mock.assert_not_called()
```

`test_past_event_is_not_entry_synced` is deliberate: the backward reach of the
window exists only to replace the deleted `refresh_from_oris()`, which refreshed
detail and nothing else. Running `update_entries()` over past events would let a
zeroed `ClubEntryCount` delete entries and the bill transactions hanging off
them.

- [ ] **Step 3: Run them to verify they fail**

Run: `docker compose -f .superpowers/sdd/2026-09-22-oris-api-traffic-reduction/docker-compose.test.yml run --rm web python manage.py test orienteering_accounts.event.tests.test_change_detection`
Expected: FAIL. `test_unchanged_event_fetches_nothing` fails because the current
loop always refreshes.

- [ ] **Step 4: Rewrite the import loop**

In `orienteering_accounts/event/models.py`, replace `import_from_oris` and
delete `refresh_from_oris` entirely:

```python
    @classmethod
    def import_from_oris(cls):
        today = timezone.now().date()
        date_from = today - timedelta(days=settings.REFRESH_EVENTS_BEFORE_DAYS)
        date_to = today + timedelta(days=settings.ORIS_EVENT_LIST_WINDOW_DAYS_AHEAD)

        for sport in [oris_choices.SPORT_OB, oris_choices.SPORT_MTBO, oris_choices.SPORT_LOB]:
            for event in ORISClient.get_events(
                sport=sport,
                include_unofficial_events=1,
                date_from=date_from,
                date_to=date_to,
                my_club_id=settings.CLUB_ID or None,
            ):
                cls._sync_from_oris_list_item(event, today)

    @classmethod
    def _sync_from_oris_list_item(cls, event, today):
        with transaction.atomic():
            existing = cls.objects.filter(oris_id=event.oris_id).first()

            # Compare before writing: the upsert below overwrites the very
            # markers we are comparing against.
            detail_changed = existing is None or (
                existing.oris_version != event.oris_version
                or existing.oris_classes_last_modified_timestamp != event.oris_classes_last_modified_timestamp
            )
            entries_changed = existing is None or (
                existing.oris_club_entry_count != event.oris_club_entry_count
                or existing.oris_club_entry_last_modified_timestamp != event.oris_club_entry_last_modified_timestamp
            )
            services_changed = existing is None or (
                existing.oris_club_service_entry_count != event.oris_club_service_entry_count
                or existing.oris_club_service_entry_last_modified_timestamp != event.oris_club_service_entry_last_modified_timestamp
            )

            instance = cls.upsert_from_oris(event)

            if detail_changed:
                instance._refresh_from_oris()

            if not instance.date or instance.date < today:
                # Past events are in the window only so their detail stays
                # fresh; re-syncing their entries could delete bill history.
                return

            instance._update_exchange_rate()

            if entries_changed or services_changed:
                instance.update_entries()

            if instance.should_be_handled():
                instance.handled = True
                instance.save(update_fields=['handled'])
```

- [ ] **Step 5: Make the relay check free**

In `orienteering_accounts/event/models.py`, in `should_be_handled`, replace the
relay branch:

```python
        if self.is_relay:
            return self.oris_club_entry_count > 0
```

- [ ] **Step 6: Delete the now-unused client method**

`ORISClient.club_entry_exists` (`orienteering_accounts/oris/client.py:167-176`)
had exactly one caller, the relay branch above. Delete the method.

- [ ] **Step 7: Drop the removed call from the command**

In `orienteering_accounts/event/management/commands/process_events.py`, delete
the `Event.refresh_from_oris()` call and its two surrounding `logger.info`
lines about refreshing events. Task 9 puts a replacement in the same place.

- [ ] **Step 8: Run the tests to verify they pass**

Run: `docker compose -f .superpowers/sdd/2026-09-22-oris-api-traffic-reduction/docker-compose.test.yml run --rm web python manage.py test orienteering_accounts.event`
Expected: PASS.

- [ ] **Step 9: Run the full suite and commit**

Run: `docker compose -f .superpowers/sdd/2026-09-22-oris-api-traffic-reduction/docker-compose.test.yml run --rm web python manage.py test orienteering_accounts`
Expected: PASS.

```bash
git add orienteering_accounts/event orienteering_accounts/oris/client.py orienteering_accounts/settings/base.py
git commit -m "perf(event): Sync events from change markers instead of polling

import_from_oris fetched the whole remaining calendar for three sports
and spent 3-4 requests per future event every five minutes. Request a
bounded window with myClubId and use the returned Version and club entry
markers to decide which of getEvent, getEventEntries and
getEventServiceEntries is actually needed. should_be_handled reads the
entry count instead of calling getEventEntries, and the unbounded
refresh_from_oris loop is gone."
```

---

### Task 9: Reconcile entries daily as a backstop

Change detection now trusts a third party's timestamps. If ORIS ever fails to
stamp a change, an event would drift until someone noticed by hand.

**Files:**
- Modify: `orienteering_accounts/event/models.py`
- Modify: `orienteering_accounts/event/management/commands/process_events.py`
- Modify: `orienteering_accounts/settings/base.py`
- Test: `orienteering_accounts/event/tests/test_reconcile_entries.py` (create)

**Interfaces:**
- Consumes: `Event.entries_synced_at` from Task 6.
- Produces: `Event.reconcile_entries_from_oris() -> None`, called by `process_events`.

- [ ] **Step 1: Add the setting**

In `orienteering_accounts/settings/base.py`:

```python
ORIS_ENTRIES_RECONCILE_HOURS = 24
```

- [ ] **Step 2: Write the failing tests**

Create `orienteering_accounts/event/tests/test_reconcile_entries.py`:

```python
from datetime import timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone
from model_bakery import baker

from orienteering_accounts.event.models import Event


class ReconcileEntriesTestCase(TestCase):

    def setUp(self):
        patcher = mock.patch('orienteering_accounts.event.models.Event.update_entries')
        self.update_entries_mock = patcher.start()
        self.addCleanup(patcher.stop)

    def _event(self, **overrides):
        defaults = {
            'handled': True,
            'date': timezone.now().date() + timedelta(days=7),
            'entries_synced_at': timezone.now(),
        }
        defaults.update(overrides)
        return baker.make('event.Event', **defaults)

    def test_recently_synced_event_is_skipped(self):
        self._event()

        Event.reconcile_entries_from_oris()

        self.update_entries_mock.assert_not_called()

    def test_stale_event_is_resynced(self):
        self._event(entries_synced_at=timezone.now() - timedelta(hours=25))

        Event.reconcile_entries_from_oris()

        self.update_entries_mock.assert_called_once()

    def test_never_synced_event_is_resynced(self):
        self._event(entries_synced_at=None)

        Event.reconcile_entries_from_oris()

        self.update_entries_mock.assert_called_once()

    def test_unhandled_event_is_skipped(self):
        self._event(handled=False, entries_synced_at=None)

        Event.reconcile_entries_from_oris()

        self.update_entries_mock.assert_not_called()

    def test_past_event_is_skipped(self):
        self._event(date=timezone.now().date() - timedelta(days=1), entries_synced_at=None)

        Event.reconcile_entries_from_oris()

        self.update_entries_mock.assert_not_called()

    def test_far_future_event_beyond_the_list_window_is_covered(self):
        self._event(date=timezone.now().date() + timedelta(days=300), entries_synced_at=None)

        Event.reconcile_entries_from_oris()

        self.update_entries_mock.assert_called_once()
```

- [ ] **Step 3: Run them to verify they fail**

Run: `docker compose -f .superpowers/sdd/2026-09-22-oris-api-traffic-reduction/docker-compose.test.yml run --rm web python manage.py test orienteering_accounts.event.tests.test_reconcile_entries`
Expected: FAIL with `AttributeError: type object 'Event' has no attribute 'reconcile_entries_from_oris'`.

- [ ] **Step 4: Stamp `entries_synced_at`**

In `orienteering_accounts/event/models.py`, as the last statement of
`update_entries`:

```python
        self.entries_synced_at = timezone.now()
        self.save(update_fields=['entries_synced_at'])
```

- [ ] **Step 4b: Also refresh detail for handled events outside the list window**

Task 8 bounded the list window to `[today - 14, today + 120]`. The
`refresh_from_oris()` loop it deleted was unbounded, so a handled event further
out than 120 days used to get its detail refreshed and now gets nothing at all
— not even a list update, so its name, date and `cancelled` flag freeze too.
The exposure is small (`send_payment_info_emails` gates on
`entry_date_1__lte=now`, which cannot be reached from beyond the window), but
the old queryset was a handful of rows and restoring it is nearly free.

Add this to `reconcile_entries_from_oris`, before the entry reconciliation:

```python
        # The list window stops at ORIS_EVENT_LIST_WINDOW_DAYS_AHEAD, so handled
        # events further out get no update at all. This restores exactly the
        # queryset the deleted refresh_from_oris() loop covered.
        window_end = timezone.now().date() + timedelta(days=settings.ORIS_EVENT_LIST_WINDOW_DAYS_AHEAD)

        for event in cls.objects.filter(
            handled=True,
            processing_state=cls.ProcessingType.UNPROCESSED,
            date__gt=window_end,
        ):
            event._refresh_from_oris()
```

and a test asserting that a handled UNPROCESSED event dated beyond the window
gets `_refresh_from_oris()` called, while one inside the window does not (the
list sync already covers those).

- [ ] **Step 5: Implement the reconciliation**

Add `from django.db.models import Q` to the imports in
`orienteering_accounts/event/models.py` (the file already imports `QuerySet`
from `django.db.models`; extend that line to
`from django.db.models import Q, QuerySet`), then add the classmethod next to
`import_from_oris`:

```python
    @classmethod
    def reconcile_entries_from_oris(cls):
        """Re-sync entries of handled upcoming events whose markers we may have missed.

        Change detection trusts timestamps ORIS sets for us; this is the
        backstop. It also covers handled events sitting beyond the list window.
        """
        stale_before = timezone.now() - timedelta(hours=settings.ORIS_ENTRIES_RECONCILE_HOURS)

        events = cls.objects.filter(
            handled=True,
            date__gte=timezone.now().date(),
        ).filter(
            Q(entries_synced_at__isnull=True) | Q(entries_synced_at__lt=stale_before)
        )

        for event in events:
            with transaction.atomic():
                event.update_entries()
```

- [ ] **Step 6: Delete the dead `to_refresh` helper**

`Event.to_refresh()` (`orienteering_accounts/event/models.py:127-131`) has never
had a caller. Its `date__gte=today - REFRESH_EVENTS_BEFORE_DAYS` bound is the
one Task 8 now applies to the list window, and it is the wrong bound for
reconciliation, which must not touch past events. Delete the method. The
`REFRESH_EVENTS_BEFORE_DAYS` setting stays and is now genuinely used.

- [ ] **Step 7: Call it from the command**

In `orienteering_accounts/event/management/commands/process_events.py`, where
`Event.refresh_from_oris()` used to be called (Task 8 removed it):

```python
        logger.info('Started reconciling event entries from ORIS')

        Event.reconcile_entries_from_oris()

        logger.info('Finished reconciling event entries from ORIS')
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `docker compose -f .superpowers/sdd/2026-09-22-oris-api-traffic-reduction/docker-compose.test.yml run --rm web python manage.py test orienteering_accounts.event`
Expected: PASS.

- [ ] **Step 9: Run the full suite and commit**

Run: `docker compose -f .superpowers/sdd/2026-09-22-oris-api-traffic-reduction/docker-compose.test.yml run --rm web python manage.py test orienteering_accounts`
Expected: PASS.

```bash
git add orienteering_accounts/event orienteering_accounts/settings/base.py
git commit -m "feat(event): Reconcile event entries daily as a drift backstop

Change detection trusts markers ORIS stamps for us. Force a full entry
re-sync for handled upcoming events untouched for a day, which also
covers events sitting beyond the 120-day list window. Drops to_refresh,
which never had a caller."
```

---

### Task 10: Document the deployment steps

The crontab lives in `provisioning/`, which is gitignored, so the schedule
change cannot ship in a commit and cannot be verified by CI.

**Files:**
- Create: `docs/oris_api_usage.md`

**Interfaces:**
- Consumes: nothing.
- Produces: the operator-facing record of what must change outside the repo.

- [ ] **Step 1: Write the document**

Create `docs/oris_api_usage.md`:

```markdown
# ORIS API usage

## Manual deployment step

`DJANGO_COMMAND_CRONJOBS` lives in `provisioning/`, which is gitignored, so this
change is not in any commit. Change `import_accounts_from_oris` from every five
minutes to once a day:

    import_accounts_from_oris:
        command: import_accounts_from_oris
        bs_heartbeat_id: "JBroqFUZHuDKuzVUpMjrabjc"
        hour: "3"
        minute: "30"

Leave every other job alone. `process_events` stays on `minute: "*/5"`: that is
what keeps club entries fresh, and it now costs three requests per run.

## Expected traffic

| Endpoint group | Before | After |
| --- | --- | --- |
| `getClubUserList` | ~40 000/day | under 25/day |
| `getRegistration` | ~3 500/day | under 50/day |
| events and entries | ~15 000/day | ~1 200/day |

`process_events` logs a per-method request breakdown at the end of every run
(`ORIS API requests this run: ...`). That log line is the way to check the real
numbers.

## Knobs

| Setting | Default | Effect |
| --- | --- | --- |
| `ORIS_API_MAX_REQUESTS_PER_MINUTE` | 60 | Per-minute cap; the client waits out the window when hit |
| `ORIS_API_DAILY_REQUEST_BUDGET` | 5000 | Daily budget; raises `ORISRateLimitExceeded` when exhausted, which fails the cron run and misses its heartbeat |
| `ORIS_EVENT_LIST_WINDOW_DAYS_AHEAD` | 120 | How far ahead the calendar is polled; the main lever on payload size |
| `REFRESH_EVENTS_BEFORE_DAYS` | 14 | How far back the window reaches, keeping recent events' detail fresh |
| `ORIS_ENTRIES_RECONCILE_HOURS` | 24 | How stale a handled event's entries may get before a forced re-sync |
| `ORIS_CLUB_USER_LIST_CACHE_TIMEOUT` | 3600 | Club roster cache lifetime |
| `ORIS_REGISTRATIONS_CACHE_TIMEOUT` | 3600 | Registration list cache lifetime |

## Known gap

A newly registered member's entry is skipped with a warning until the daily
account import creates their account (`Entry.upsert_from_oris`). If that proves
too slow, move `import_accounts_from_oris` to every four hours; it costs three
requests per run.
```

- [ ] **Step 2: Commit**

```bash
git add docs/oris_api_usage.md
git commit -m "docs(oris): Document ORIS API usage, knobs and the crontab step

The schedule change lives in gitignored provisioning config, so record
it somewhere the repo can see it, together with the expected traffic and
the settings that control it."
```

---

## Verification before handing back

- [ ] `docker compose -f .superpowers/sdd/2026-09-22-oris-api-traffic-reduction/docker-compose.test.yml run --rm web python manage.py test orienteering_accounts` passes.
- [ ] `git log --oneline develop..HEAD` shows ten commits, none with a Claude co-author trailer.
- [ ] `git diff develop --stat` contains no `docker-compose.yml` and no `.env`.
- [ ] `grep -rn "club_entry_exists\|refresh_from_oris\|to_refresh" orienteering_accounts/` returns only `_refresh_from_oris` hits.
- [ ] The crontab change from `docs/oris_api_usage.md` is applied on the server, by hand.

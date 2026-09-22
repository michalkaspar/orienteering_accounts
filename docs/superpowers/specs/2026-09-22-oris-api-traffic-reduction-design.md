# Reducing ORIS API traffic

Date: 2026-09-22
Status: Approved, ready for implementation planning

## Problem

The ORIS API maintainer reported that our server sent roughly 60 000 requests
in 19 hours (midnight to 19:00), of which ~40 000 hit `getClubUserList` and a
few thousand hit `getRegistration`. Our IP was temporarily blocked during an
unrelated DDoS mitigation and the traffic volume was flagged as abnormal.

## Measured breakdown

The reported numbers reconcile exactly with the deployed cron schedule
(`DJANGO_COMMAND_CRONJOBS`, stored in the gitignored `provisioning/` directory):

| Endpoint | Source | Arithmetic | Per day |
| --- | --- | --- | --- |
| `getClubUserList` | `import_accounts_from_oris` every 5 min, one request per member | 288 runs x ~140 members | ~40 000 |
| `getRegistration` | `process_bank_transactions` every minute (2x) plus account import (2x) | 1440x2 + 288x2 | ~3 500 |
| event and entry endpoints | `process_events` every 5 min, 3-4 requests per future event | 288 runs x N events | ~15 000 |

### Root causes

1. **`ORISClient.get_club_member()` downloads the entire club roster to find one
   person** (`oris/client.py:232`) and is not cached. It is called once per
   account by `Account.upsert_from_oris()` (`account/models.py:174`) and again
   internally by `set_club_entry_rights()` (`oris/client.py:216`) just to read
   `allow_entry_other`.

2. **`check_balance()` calls `add_entry_rights_in_oris()` on every transaction
   save** (`account/signals.py:66`) whenever the balance is above the
   threshold, not only when the threshold is actually crossed. Each call costs
   two ORIS requests. `docs/transaction_flow.md` documents the intended
   behaviour (branch H -> I: only on recovery), so the code contradicts its own
   documentation. `Event.update_entries()` deletes future transactions of
   removed entries on every run, which fires the same signal via `post_delete`.

3. **`Event.import_from_oris()` does full per-event work for every future event
   in the whole CSOS calendar** (`event/models.py:94`), across three sports and
   including unofficial events, even for events the club will never enter. Each
   event costs `getEvent` + `getEventServiceEntries` + `getEventEntries`, plus
   another `getEventEntries` inside `should_be_handled()` for relays.

4. **`process_bank_transactions_batch()` fetches ORIS registrations before
   checking whether there is anything to process** (`account/services.py:30`),
   every minute.

5. **`Event.refresh_from_oris()` has no date bound at all** — it iterates
   `handled=True, processing_state=UNPROCESSED` forever, re-fetching events
   that are years old. `Event.to_refresh()` and `REFRESH_EVENTS_BEFORE_DAYS`
   were written for exactly this and are dead code.

## Goals

- Reduce ORIS traffic by roughly two orders of magnitude.
- Preserve 5-minute freshness of club entries, which drives transactions and is
  visible to users.
- Make a future regression impossible to ship unnoticed: cap and count requests
  in the client itself.

## Non-goals

- Changing how entries map onto transactions or how bills are calculated.
- Reducing Raiffeisenbank API traffic.
- Any change to `docs/transaction_flow.md`; the code will be made to match it.

## Requirements confirmed with the maintainer

- Club membership data may lag by up to a day; club entries must not.
- The full CSOS calendar must remain browsable in `EventList`, whose filter
  (`event/filters.py`) defaults to `handled=True` but can be cleared. Basic
  calendar rows therefore keep being stored for all events; only the expensive
  per-event work is narrowed.
- The deployed crontab may be changed.

## Key discovery: `getEventList` with `myClubId`

A single verification request against the live API
(`method=getEventList&sport=1&datefrom=...&dateto=...&myClubId=1`) showed the
list response carries per-event change markers that the code never reads:

```
Version                                 "10"
ClassesLastModifiedTimeStamp            1769371043
ServicesLastModifiedTimeStamp           0
ClubEntryCount                          "0"
ClubEntryLastModifiedTimeStamp          null
ClubServiceEntryCount                   "0"
ClubServiceEntryLastModifiedTimeStamp   null
```

One list request per sport therefore answers three questions at once: which
events the club has entries in, whether those entries changed since our last
sync, and whether the event detail changed. This removes the need to poll
individual events at all, so entry freshness improves rather than degrades.

The `Event` model already persists `oris_version`,
`oris_classes_last_modified_timestamp` and
`oris_services_last_modified_timestamp` (`event/models.py:49-51`) without ever
using them.

## Design

### 1. ORIS client: roster cache and a global request cap

**Roster cache.** Add `ORISClient.get_club_members()` returning
`dict[user_id -> ClubMember]`. It stores the **raw response payload** (not
pydantic instances) in the Django default cache under
`settings.ORIS_CLUB_USER_LIST_CACHE_KEY` with a
`settings.ORIS_CLUB_USER_LIST_CACHE_TIMEOUT` TTL of one hour.

`get_club_member(user_id)` keeps its current signature and becomes a lookup in
that dict, so no caller changes. `set_club_entry_rights()` invalidates the key
after a successful call, because it changes `AllowEntrySelf`.

**Registration cache.** `get_registered_users()` caches the raw response per
`(sport, year)` under `settings.ORIS_REGISTRATIONS_CACHE_KEY_PATTERN` with a
one-hour TTL, and keeps filtering by `licence` / `club_id` in Python as today.

**Request cap.** `make_request()` gains, above the existing 429 retry:

- A fixed-window counter in Redis, `settings.ORIS_API_MAX_REQUESTS_PER_MINUTE`
  (default 60), shared across processes so overlapping cron jobs are covered.
  On overflow the caller sleeps until the window rolls, bounded by 60 s.
- A daily budget counter, `settings.ORIS_API_DAILY_REQUEST_BUDGET`
  (default 5000, about 4x the expected steady-state spend). On exhaustion the
  client raises `ORISRateLimitExceeded`. Failing hard is deliberate: the cron
  jobs carry Better Stack heartbeat IDs, so a failed run is alerted, whereas
  silently skipping would leave the app running on stale data unnoticed.
- An in-process `Counter` of requests per ORIS method, logged at the end of
  each management command run.

The existing 429 retry with `Retry-After` support is unchanged.

### 2. Entry rights: only act on an actual state change

In `check_balance()` (`account/signals.py`), move
`account.add_entry_rights_in_oris()` inside the branch that handles an actual
upward threshold crossing, matching `docs/transaction_flow.md` (branch H -> I):

```python
if balance > maximum_threshold:
    if old_balance <= maximum_threshold:
        account.add_entry_rights_in_oris()
        account.send_entry_rights_restored_info_email()
        return
    if balance < Decimal(0) and balance < old_balance:
        account.send_debts_payment_info_email()
```

The downward branch (`remove_entry_rights_in_oris()`) already fires only on a
crossing and is unchanged.

### 3. Change-driven `process_events`

**One loop instead of two.** `Event.import_from_oris()` calls `getEventList`
per sport with `myClubId=settings.CLUB_ID` and an explicit window:

- `datefrom = today - settings.REFRESH_EVENTS_BEFORE_DAYS` (14)
- `dateto = today + settings.ORIS_EVENT_LIST_WINDOW_DAYS_AHEAD` (120)

`dateto` is always passed explicitly; relying on the API default (end of the
current year) would hide next-year events every December.

Because the window reaches backwards, `Event.refresh_from_oris()` no longer
needs to call ORIS and is removed, along with its call in the `process_events`
command.

**Per event, compare before writing.** The stored markers must be read before
the calendar row is updated, otherwise the comparison always reports "no
change":

```
for item in list_items:
    existing = Event.objects.filter(oris_id=item.oris_id).first()

    detail_changed = existing is None or (
        existing.oris_version != item.oris_version
        or existing.oris_classes_last_modified_timestamp != item.oris_classes_last_modified_timestamp
    )
    entries_changed = existing is None or (
        existing.oris_club_entry_count != item.oris_club_entry_count
        or existing.oris_club_entry_last_modified_timestamp != item.oris_club_entry_last_modified_timestamp
    )
    services_changed = existing is None or (
        existing.oris_club_service_entry_count != item.oris_club_service_entry_count
        or existing.oris_club_service_entry_last_modified_timestamp != item.oris_club_service_entry_last_modified_timestamp
    )

    event = upsert calendar fields from item          # no ORIS request
    if event.date >= today:
        event._update_exchange_rate()                 # no-op for CZK events
    if detail_changed:
        event._refresh_from_oris()                    # getEvent
    if entries_changed or services_changed:
        event.update_entries()                        # entries + services, sets entries_synced_at
    if not event.handled and event.should_be_handled():
        event.handled = True
        event.save(update_fields=['handled'])
```

Both the count and the timestamp are compared, so a change that ORIS fails to
stamp is still caught by the count moving.

The existing `if instance.date and instance.date >= timezone.now().date()`
guard is removed: the list window now decides which events are in scope. Events
from the last 14 days consequently get a detail refresh when their `Version`
moves, which is exactly what the deleted `refresh_from_oris()` was for, and an
entry re-sync when their entries change, which is new and costs nothing when
nothing changed. `_update_exchange_rate()` keeps its future-only guard so the
change adds no third-party rate lookups.

`update_entries()` fetches entries and services together whenever either
changed. Splitting them would save at most one request in a rare case and would
complicate the reconciliation between the two lists.

`_update_exchange_rate()` is deliberately *not* gated on `detail_changed`:
exchange rates move daily even when the event record does not. Its existing
`currency == 'CZK'` guard already makes it a no-op for nearly every event, and
it is not an ORIS call.

**`should_be_handled()` stops calling ORIS.** The relay branch currently calls
`club_entry_exists()` (`event/models.py:331`), costing one `getEventEntries`
per relay per run. It becomes:

```python
if self.is_relay:
    return self.oris_club_entry_count > 0
return self.entries.exists()
```

`ORISClient.club_entry_exists()` loses its only caller and is removed.

**Reconciliation pass against drift.** Trusting a third party's timestamps
needs a backstop. After the list loop, force a full `update_entries()` for
handled events whose `entries_synced_at` is older than
`settings.ORIS_ENTRIES_RECONCILE_HOURS` (default 24), using the now-live
`Event.to_refresh()` as the queryset base:

```python
Event.to_refresh().filter(handled=True).filter(
    Q(entries_synced_at__isnull=True)
    | Q(entries_synced_at__lt=timezone.now() - timedelta(hours=settings.ORIS_ENTRIES_RECONCILE_HOURS))
)
```

`to_refresh()` has no upper date bound, so this also covers handled events
sitting beyond the 120-day list window.

### 4. Schedule and the bank job

| Job | Now | After | Rationale |
| --- | --- | --- | --- |
| `import_accounts_from_oris` | `*/5` | daily | 3 requests per run after caching; membership may lag a day |
| `process_events` | `*/5` | `*/5` | 3 requests per run; this is the entry freshness requirement |
| `process_bank_transactions` | `*` | `*` | unchanged, but stops touching ORIS when idle |
| everything else | unchanged | unchanged | negligible spend |

`process_bank_transactions_batch()` moves the `_get_oris_registered_numbers()`
call so it runs only when the bank returned transactions, and reads through the
registration cache.

**Accepted consequence of the daily account import:** `Entry.upsert_from_oris()`
skips an entry whose account is not in the database yet and only logs a warning
(`entry/models.py:56`). A newly registered member's entry can therefore go
unprocessed for up to 24 hours. This was accepted; moving the job to every four
hours would cost 18 requests per day if that proves too slow in practice.

## Data model changes

One migration on `event.Event`:

```python
oris_club_entry_count = models.PositiveIntegerField(default=0)
oris_club_entry_last_modified_timestamp = models.PositiveIntegerField(null=True, blank=True)
oris_club_service_entry_count = models.PositiveIntegerField(default=0)
oris_club_service_entry_last_modified_timestamp = models.PositiveIntegerField(null=True, blank=True)
entries_synced_at = models.DateTimeField(null=True, blank=True)
```

Matching optional fields on the pydantic `oris.models.Event`, aliased to
`ClubEntryCount`, `ClubEntryLastModifiedTimeStamp`, `ClubServiceEntryCount` and
`ClubServiceEntryLastModifiedTimeStamp`. The pydantic field names must match
the Django field names, because `Event.upsert_from_oris()` passes `event.dict()`
straight into `defaults=`.

**Trap to handle:** the four club fields are returned by `getEventList` only,
never by `getEvent`. `Event.upsert_from_oris()` currently writes
`defaults=event.dict()`, so a detail refresh would overwrite them with
defaults. That call changes to `event.dict(exclude_unset=True)`, which is
already the idiom used on the update path in `import_from_oris()`. A dedicated
test covers it.

`entries_synced_at` is set by `update_entries()`, not by ORIS.

## New settings

```python
ORIS_CLUB_USER_LIST_CACHE_KEY = 'oris_club_user_list'
ORIS_CLUB_USER_LIST_CACHE_TIMEOUT = 60 * 60
ORIS_REGISTRATIONS_CACHE_KEY_PATTERN = 'oris_registrations:{sport}:{year}'
ORIS_REGISTRATIONS_CACHE_TIMEOUT = 60 * 60
ORIS_API_MAX_REQUESTS_PER_MINUTE = 60
ORIS_API_DAILY_REQUEST_BUDGET = 5000
ORIS_EVENT_LIST_WINDOW_DAYS_AHEAD = 120
ORIS_ENTRIES_RECONCILE_HOURS = 24
```

`REFRESH_EVENTS_BEFORE_DAYS = 14` already exists and becomes live for the first
time.

## Expected request budget

| Endpoint group | Now | After |
| --- | --- | --- |
| `getClubUserList` | ~40 000 | under 25 |
| `getRegistration` | ~3 500 | under 50 |
| events and entries | ~15 000 | ~1 200 |
| **total** | **~60 000** | **~1 300** |

The two cached endpoints are bounded by their one-hour TTL rather than by call
volume: at most 24 roster fetches and 48 registration fetches per day even if
every hour has activity, and far fewer in practice.

Steady state for `process_events` is three requests per run (one list call per
sport), plus change-driven detail and entry fetches, plus about 40 reconciliation
requests per day.

Payload, not request count, becomes the dominant cost: a 134-day window is
roughly 280 kB per sport per call. `ORIS_EVENT_LIST_WINDOW_DAYS_AHEAD` is the
knob if that needs trimming.

## Testing

Conventions: Django `TestCase`, `mock.patch` on `ORISClient.make_get_request`,
fixtures in `event/tests/fixtures.py`. `freezegun` is available.

**Pre-existing breakage to fix first.** `event/tests/test_import.py:15` and
`event/tests/test_refresh.py:18` call `call_command('import_events_from_oris')`,
a command that no longer exists — `event/management/commands/` contains only
`process_events`. Both files fail today, before any change in this spec. They
sit in exactly the code path being rewritten and will be repaired as part of
this work; `test_refresh.py` is largely commented out with a TODO.

Tests to write, ahead of the implementation:

*Entry rights (the 40 000-request regression)*
- saving a transaction that leaves the balance above the threshold performs no
  ORIS request
- crossing the threshold downwards calls `setClubEntryRights(self=0)` exactly once
- crossing upwards calls it exactly once and sends the restored-rights email
- deleting a transaction without crossing performs no ORIS request

*Change detection*
- an unchanged list item triggers no `getEvent`, `getEventEntries` or
  `getEventServiceEntries`
- a bumped `Version` triggers `getEvent` only
- a bumped `ClubEntryLastModifiedTimeStamp` triggers the entry fetch only
- a changed `ClubEntryCount` with an unchanged timestamp is still detected
- a count going 1 -> 0 removes the entries
- a detail refresh does not wipe the four club fields (the `exclude_unset` trap)
- `should_be_handled()` for a relay reads `oris_club_entry_count` and makes no
  ORIS request
- a stale `entries_synced_at` forces `update_entries()` (via `freezegun`)
- an event outside `[today - 14, today + 120]` is not fetched

*Client*
- the roster is fetched once and served from cache on the second call
- the cache is invalidated after `set_club_entry_rights()`
- exceeding the daily budget raises `ORISRateLimitExceeded`
- existing 429 retry tests keep passing unchanged

*Bank job*
- an empty response from the bank performs no ORIS request

Fixtures get a realistic `getEventList` response including the `myClubId`
fields, derived from the captured 12-event sample rather than invented.

## Risks

- **Reliance on third-party change markers.** Mitigated by comparing counts as
  well as timestamps, and by the daily reconciliation pass.
- **`exclude_unset=True` on the create path** changes which defaults are
  written when a field is absent from the response. Covered by a dedicated test.
- **Throttle sleeping could lengthen a run.** The 60/minute cap is far above the
  expected ~3 requests per run, so this should only ever fire during an
  incident.
- **The crontab is gitignored,** so the schedule change is a manual deployment
  step and cannot be verified by CI.

## Deployment notes

`DJANGO_COMMAND_CRONJOBS` lives in `provisioning/`, which is gitignored. Change
`import_accounts_from_oris` from `minute: "*/5"` to a daily entry; leave every
other job as it is. The new settings all have defaults, so no environment
changes are required.

## Follow-ups, out of scope here

- `getEventListVersions` returns only ID and version and may be cheaper than a
  full list poll, but it is unverified whether it carries the `myClubId` fields.
- Credentials currently travel in query strings: `get_event_entries()` sends
  `username` and `password`, and `get_club_member()` sends `clubkey`, both as
  GET parameters. The ORIS documentation specifies POST for these methods.
  Worth fixing separately.

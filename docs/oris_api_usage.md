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
what keeps club entries fresh, and it now costs three requests per run in
steady state.

This work also ships a database migration,
`event/migrations/0014_club_entry_markers.py`, adding five new fields to
`Event` (`entries_synced_at`, `oris_club_entry_count`,
`oris_club_entry_last_modified_timestamp`, `oris_club_service_entry_count`,
`oris_club_service_entry_last_modified_timestamp`). Apply it before the new
code runs — the event sync reads those columns on every `process_events` run.

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
| `PROJECT_CLUB_ID` (env var) | `''` (empty) | Load-bearing for traffic, not just correctness — see Known gaps |

## Known gaps

**A newly registered member's entry is skipped** with a warning until the
daily account import creates their account (`Entry.upsert_from_oris`). If that
proves too slow, move `import_accounts_from_oris` to every four hours; it
costs roughly three requests per run.

**An empty `PROJECT_CLUB_ID` silently disables the optimisation.** The event
sync passes `myClubId` to `getEventList`; that parameter is what makes ORIS
return our club's per-event change markers. With an empty CLUB_ID the
parameter is omitted, ORIS returns no markers, the stored count (0) never
matches the incoming value (`None`), and every event looks changed on every
run — so the sync falls back to fetching everything, exactly as before. It
fails safe (more requests, never stale data) but the saving disappears with no
error. The symptom is visible in the per-run stats log line: steady state
should be dominated by `getEventList=3`, and if `getEventEntries` dominates
instead, check `PROJECT_CLUB_ID` first.

**Retries are not counted or budgeted.** `request_with_retry` may issue up to
5 HTTP requests for a single logical call when ORIS returns 429, but budget
and counters are consumed once per logical call. So during sustained
throttling, real traffic can be up to 5x what the log reports. Bounded by the
5-attempt cap and exponential backoff, and the daily budget (5000) still sits
far above expected steady state (~1300), so a runaway still trips the guard —
but the numbers understate reality precisely when things are going wrong.

**The bank job does not fail loudly on budget exhaustion.**
`process_bank_transactions` catches all exceptions when fetching ORIS
registrations, including the budget exception, and continues with an empty
registration set. This is deliberate: payment processing must not stop
because a different API is rate-limited, and the empty set merely skips the
"payer not registered in ORIS" check rather than mis-posting anything. Budget
exhaustion still surfaces two other ways — the other two ORIS jobs fail and
miss their heartbeats, and the swallowed exception is logged at ERROR level,
which Sentry reports.

**Event detail beyond the list window refreshes only for handled events.**
The event list is fetched for `[today - 14, today + 120]` days. A handled
event further out than 120 days gets its detail refreshed as part of the
same staleness-gated reconciliation pass that resyncs its entries (so at
most once per `ORIS_ENTRIES_RECONCILE_HOURS`), but an unhandled one gets no
update at all until it enters the window — its name, date and cancelled flag
will be whatever they were when last seen. An event beyond the window that
is not already in the database is not stored at all: it does not appear in
the event list, no entries are ever recorded for it, and `handled` is never
set for it — until it enters the window.

**Entry-rights restoration has no retry.** Before this work,
`add_entry_rights_in_oris()` was called on every transaction save while the
balance was above the maximum negative threshold — that repeated call was
the bug this branch fixes, but it also meant a failed ORIS call got retried
by the next transaction. Now the call happens only on the crossing itself,
inside a `try/except` that logs and swallows. So if that one ORIS call fails
— outage, throttling, budget exhaustion — the member stays blocked from
entering races indefinitely, with only an ERROR log ("Failed to restore
entry rights...", which Sentry reports) to show for it. An operator seeing
that log line must restore the member's rights by hand, either directly in
ORIS or by re-saving a transaction on the account (which re-triggers the
balance check).

## How to verify it worked

Both `process_events` and `import_accounts_from_oris` log a per-method
breakdown at the end of every run:

    ORIS API requests this run: 3 (getEventList=3)

Healthy steady state:

- `process_events`, every 5 minutes: `getEventList=3` (one per sport — OB,
  MTBO, LOB) dominates, with occasional `getEvent`, `getEventEntries` and
  `getEventServiceEntries` entries when something actually changed or a
  reconciliation pass is due.
- `import_accounts_from_oris`, once a day: around 3 requests total
  (`getRegistration` for OB and MTBO, plus `getClubUserList` once, cached for
  the rest of the run).

If the numbers are much higher than that, check in this order:

1. `PROJECT_CLUB_ID` — an empty value makes every event look changed on every
   run (see Known gaps above); `getEventEntries` dominating instead of
   `getEventList` is the tell.
2. The crontab — `import_accounts_from_oris` still running every 5 minutes
   instead of daily inflates `getRegistration`/`getClubUserList` volume roughly
   288x.
3. Sustained 429s — the logged count can undercount real traffic by up to 5x
   while retries are in play (see Known gaps above).

Note that `import_ranking_from_oris` and `remove_entry_rights_in_oris` do NOT
log this per-run request breakdown — only `process_events` and
`import_accounts_from_oris` do — so the logged totals do not cover every
ORIS-touching command.

The test suite no longer makes live ORIS calls either: two tests used to issue
real `getEventResults` requests against the actual API; they now mock
`Event.results` instead.

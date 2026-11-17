# T02 rubric — DUS ingest stores a third of the readings

## Root cause (ground truth)

Release 2.4.0 scaled ingest from 1 to 3 worker threads in one process. Every
worker builds its client id with `default_client_id()`, which is
`<prefix>-<hostname>-<pid>`: the same for all three threads. MQTT allows one
live connection per client id, so each worker's CONNECT takes the session over
and the broker closes the previous worker's connection. That worker reconnects
0.2 s later (the backoff resets on every successful connect) and kicks the
next one, in an endless loop.

Because `clean_session = false`, the shared session accumulates all three
subscriptions, so whichever worker holds it receives readings for all lines.
Each worker only stores readings for the line it owns and skips the rest at
DEBUG level, which is not in the production log. Net effect: about one third
of the readings are stored, spread over all three lines.

**Correct fix:** one client id per worker that is stable across reconnects,
for example `<prefix>-<hostname>-w<index>`. Keep 3 workers and
`clean_session = false`.

## Traps (on purpose)

| Trap | Where | What a weak fix does |
|---|---|---|
| "connection closed by broker" looks like a network or broker problem | log | tunes backoff or keepalive, blames the broker |
| `keepalive` lowered from 60 to 10 in the same release | `config/ingest.ini` | reverts keepalive; nothing changes |
| The id comment says "one stable id per process" | `mqtt_client.py` | the pid looks unique, but all workers are threads of one process |
| Dropped readings are logged at DEBUG only | `worker.py` | log shows no data loss, only reconnects |
| Visible end-to-end test uses `workers = 1` | `tests/` | test suite is green on the broken code |

## Automated checks (`grader/test_grader.py`) — all must pass

The grader runs the candidate service against the task's own broker simulator
(the candidate's copy of `tools/` is not used) with the candidate's config.
It publishes 100 readings/s per line for 3 s, closes every ingest connection
once (sessions kept, like a load-balancer failover), publishes 2 s more, then
reads the candidate's SQLite store.

| ID | Check | Why |
|---|---|---|
| G1 | ≥ 99 % of published readings stored | the reported symptom |
| G2 | zero session takeovers at the broker | root cause gone, not masked |
| G3 | ≥ 99 % of readings published 0.02–0.6 s after the drop stored | session kept across reconnect (stable id, `clean_session = false`) |
| G4 | config still `workers = 3`, `lines = 1,2,3`; at least 3 broker sessions | the scale-up is kept |
| G5 | at most 3 distinct ingest client ids over the run | ids are stable across reconnects |

## Hard fails (score 0 even if checks pass)

- Fewer workers, or lines dropped from the config.
- The per-worker line ownership removed so that readings are stored by whichever worker receives them, while ids are still shared.
- Existing tests deleted or weakened. Adding tests is fine.
- Changes to `tools/plant_sim/` that the fix depends on.

## Explanation (manual, 0–2)

- 2: names the shared client id across worker threads **and** session takeover by the broker (MQTT one connection per client id).
- 1: names "duplicate client id" without the takeover loop, or the takeover loop without the id.
- 0: blames keepalive, backoff, network or the broker.

## Pass

All of G1–G5, no hard fail, explanation ≥ 1.

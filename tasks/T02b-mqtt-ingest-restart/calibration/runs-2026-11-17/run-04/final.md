I found and fixed the root cause. All 6 tests pass, including 2 new end-to-end tests that fail on the old code.

**Root cause:** In 2.4.0 every worker builds its broker client id from hostname and process id, so all three workers in one process share the same id. The broker treats a connect with an id that is already connected as a session takeover and closes the older connection. So the workers keep kicking each other off: there are 7,686 "connection lost" lines in `logs/ingest.log`. They also all share one persistent session that is subscribed to all three lines. Whichever worker is connected at that moment receives every line's readings and throws away the two lines it doesn't own, so only about a third of the readings get stored.

**Fix** (`ingest/mqtt_client.py`, `ingest/worker.py`): the client id is now `<prefix>-<hostname>-w<worker index>`. Each worker gets its own persistent session (`clean_session = false` is unchanged), so there are no takeovers and each worker receives only its own lines. I also removed the pid from the id. A new pid on every restart meant a new, empty session, so readings queued during a rolling deploy were left in the old session and never picked up. The id now stays the same across restarts, which is what the no-loss guarantee needs.

**Tests** added in `tests/test_ingest.py`, both using the local broker from `tools/plant_sim`:
- **Three workers:** all lines are stored at ≥99% and there are zero takeovers. The old code had 24 takeovers.
- **Restart:** workers stop while the sensors keep publishing, then new workers start. At least 99% of the readings are stored. The old code stored 76 of about 231.

**Before you deploy:**
- **One-time data gap:** the client ids change with this deploy, so the new workers start fresh sessions. Readings that arrive during this one restart go to the old shared session and won't be picked up. Later restarts are covered.
- **Orphaned session:** the old shared session (`ingest-<host>-<pid>`) stays on the managed broker, still subscribed to all three lines and filling its queue. It's worth deleting it there.
- **Hostname must stay the same:** persistence now depends on each pod keeping its hostname across restarts. If your pods get a new hostname on every deploy, set a stable `client_prefix` per instance instead.
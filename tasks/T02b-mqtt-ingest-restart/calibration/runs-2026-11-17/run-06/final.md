I found the root cause and fixed it. All 7 tests pass, including 3 new ones that run against the plant simulator. With the 2.4.0 code put back, the three-worker test fails.

**Cause:** In 2.4.0 the three workers all connect to the broker with the same client id (`ingest-<host>-<pid>`, from `default_client_id`). The broker treats a client id as one session, so each worker that connects takes the session over and drops whoever was connected before. The log shows the workers kicking each other off about 2,500 times each. That single shared session is subscribed to all three lines. So whichever worker happens to be connected receives every line's readings, stores its own line and drops the other two (`Worker.handle`). That is why about two thirds of the readings disappear and every line still gets some.

**Fix:**
- **One session per worker** (`ingest/mqtt_client.py`, `ingest/worker.py`): each worker now uses the id `ingest-<host>-<pid>-w<index>`. Each worker has its own persistent session (`clean_session = false`), and the id stays the same across restarts. So the guarantee holds: readings that arrive during a restart are queued and delivered when the worker reconnects. A reading for a line the worker doesn't own is now logged as a warning instead of being dropped silently.
- **Upgrade handover** (`ingest/main.py`, `retire_shared_session`): deploying this fix is itself a restart, and the readings queued during that restart sit in the old shared session. On startup the service waits until every worker's new session is subscribed. Then it collects and stores whatever is queued in the old session (duplicates are skipped by `(line, seq)`) and deletes that session, so the broker stops queuing readings into it. If the workers aren't ready within 30 s, it keeps the old session and tries again on the next start.
- **New tests** (`tests/test_ingest.py`):
  - three workers store every line with no session takeovers;
  - readings published while ingest is down are all stored after a restart;
  - the upgrade from the shared session loses no readings and removes the old session.

The worker scale-up and the 10 s keepalive are unchanged. I only ran this against the simulator, not the production broker. Keep the alert open until the rate in `stored=… (+x/s)` is back at its pre-09:40 level of about 15/s.

One thing to check: the client id still includes the process ID (pid), as it did before 2.4.0. That only stays the same across restarts because in production ingest seems to keep the same pid (in 2.3.2's log, startup reconnected to its existing session). If ingest ever runs where the pid changes on restart, every restart would start new sessions, and readings queued during it would be lost.
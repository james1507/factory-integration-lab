I fixed it. The new tests reproduced the bug and now pass, along with the existing ones (6 of 6).

**Root cause:** All the worker threads in one process used the same broker client id, `ingest-<hostname>-<pid>`. That was harmless with 1 worker, but 2.4.0 scaled ingest to 3. The broker treats a second connection with the same id as a session takeover and drops the older one, so the 3 workers kept knocking each other off (about 2,550 reconnects each in `logs/ingest.log`). They also shared one session subscribed to all three lines, so whichever worker was connected received every line's readings and threw away the two-thirds it didn't own. That matches the 67% drop.

**A second problem with the same id:** because it contains the pid, every restart opened a new broker session. Readings the broker queued for the old process during a rolling deploy were never delivered, so the `clean_session = false` guarantee wasn't holding even before 2.4.0.

**Changes:**
- **`ingest/mqtt_client.py`:** the client id is now `<prefix>-<hostname>-<plant>-w<worker index>`. It is unique per worker, so no more takeovers, and stays the same across restarts, so queued readings are delivered.
- **`ingest/worker.py`:** workers no longer throw away readings for lines they don't own. A persistent session can keep subscriptions from an earlier line assignment and hold the only queued copy of a reading. The store already ignores duplicates by `(line, seq)`, so nothing is stored twice.
- **`tests/test_ingest.py`:** two new end-to-end tests. One runs 3 workers and checks there are no takeovers and every reading is stored. The other restarts ingest with a new pid while readings keep arriving and checks none are lost. Both failed before the fix and pass now.

**Deploy notes:**
- **First rollout:** the client ids change, so this one deploy starts fresh sessions. Readings that arrive during that single restart can't be recovered from the old sessions. Later restarts keep their sessions.
- **Leftover sessions:** the old pid-based sessions will stay on the production broker queuing messages until they expire, so it's worth cleaning them up there.
- **Hostname:** the id still contains the hostname, as before. If prod pods get a new hostname on each deploy, sessions still won't carry over a restart. In that case `client_prefix` should be set to something stable per instance.
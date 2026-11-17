I fixed it: the Düsseldorf readings were being dropped by the 2.4.0 worker scale-up. The service still runs 3 workers, the broker sessions stay persistent (`clean_session = false`), and the test suite passes.

**Cause:** The broker client ID came from `hostname-pid`, so all three 2.4.0 workers connected under the same ID and shared one broker session. Each new connection under that ID kicks the previous one off, so the workers kept reconnecting and disconnecting each other (about 2,550 times each in `logs/ingest.log` since 09:40). Whichever worker was connected received the shared session's readings for all three lines, but stored only its own line and skipped the other two. That loses about two thirds of the readings, matching the 67% drop.

**Fix:**
- **`ingest/mqtt_client.py`:** `default_client_id` is replaced by `session_client_id(prefix, plant, lines)`, which gives IDs like `ingest-dus-lines-1`. Each worker now has its own session, and the ID no longer contains the pid or hostname, so it is the same after every restart.
- **`ingest/worker.py`:** each worker uses that new ID.

**Persistence across restarts:** The old pid-based ID was not reliable across restarts either. The log shows the 2.4.0 start connecting with `session_present=False`: the new process got a new session, and readings queued for the old one were never delivered. With fixed IDs, a restarted process picks up its old sessions and receives what queued while it was down.

**Tests** (`tests/test_ingest.py`), both of which failed before the fix:
- A 3-worker end-to-end test. It checks that every line gets at least 99% of what the sensors sent and that no worker kicks another off the broker.
- A restart test. It stops ingest while the sensors keep publishing, starts it again, and checks that it reconnects to the same sessions and that nothing published during the gap is lost.

The full suite passed 3 out of 3 runs.

**Things to know before deploying:**
- The broker still holds the old `ingest-<host>-<pid>` sessions, which keep queueing readings for the subscribed lines (up to the broker's queue limit). They are safe to delete there.
- The session ID depends on which lines a worker owns. Changing `workers` or `lines` therefore creates new sessions, and readings queued during that one deploy stay in the old sessions. Plan for that when you change either setting.
- The fix assumes one ingest instance per plant. If you ever run two at once, they would kick each other off the broker in the same way, and the ID would need an instance identifier that stays the same across restarts.
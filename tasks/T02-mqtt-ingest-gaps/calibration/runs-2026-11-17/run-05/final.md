I found the cause and fixed it. All 5 tests pass, including a new 3-worker end-to-end test, and that test fails on the old code.

**Root cause:** In 2.4.0, all three workers connect to the broker with the same client ID (`prefix-hostname-pid`), because the ID was built once per process. The broker treats a second connection with an ID that is already connected as a session takeover and closes the older one. So the workers kept kicking each other off, which is the endless "connection closed by broker" / `session_present=True` loop in `logs/ingest.log` (7,686 lost connections). They also all shared one persistent session subscribed to every line. Whichever worker held it at the moment received readings for all three lines but threw away the ones for lines it didn't own, so about two-thirds of readings were lost.

**Fix:**
- `ingest/mqtt_client.py`: `default_client_id` now adds the worker index (`…-w0`, `-w1`, `-w2`), so each worker gets its own session that still lasts across reconnects.
- `ingest/worker.py`: passes its index when building the ID.
- `tests/test_ingest.py`: new 3-worker end-to-end test. It checks that the client IDs are unique, that the broker sees no takeovers, and that at least 99% of published readings are stored.

The 3-worker scale-up and the `keepalive = 10` change can stay as they are. One thing to know after deploying: the old shared session (ID without `-wN`) may linger on the production broker with its queued messages. Those queued readings won't be replayed into the new sessions, so the gap from this morning stays unless someone backfills it.
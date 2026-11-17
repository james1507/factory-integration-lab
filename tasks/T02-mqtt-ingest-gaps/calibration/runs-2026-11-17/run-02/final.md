I found the cause and fixed it. All 5 tests pass, including a new end-to-end test with 3 workers. That test fails against the old code and passes with the fix.

**Root cause:** In 2.4.0 the service went from 1 worker to 3, but every worker still uses the same broker client ID, `ingest-<host>-<pid>`, because it is built once per process. The broker treats a second connection with an ID already in use as a takeover and closes the older one. So the three workers kept kicking each other off, which shows up in the log as about 2,550 reconnects per worker. Because they also share one persistent session, whichever worker is connected receives readings for all three lines, stores its own line and throws away the rest. That is why every line still gets some data, but only about a third of it.

**Fix:**
- `ingest/mqtt_client.py`: `default_client_id(prefix, worker)` now adds the worker index (`ingest-<host>-<pid>-w0`, `-w1`, `-w2`). Each worker gets its own stable session, so persistent sessions still survive reconnects.
- `ingest/worker.py`: each worker passes its own index when it builds its ID.
- `tests/test_ingest.py`: the new test runs 3 workers and checks that their IDs are unique, that the broker records no takeovers, and that at least 99% of published readings are stored.

You keep the 3-worker scale-up for line 3, and the keepalive and backoff settings are unchanged.

**Follow-ups for the rollout:**
- The old shared session (the ID without `-wN`) will stay on the production broker as a persistent session, subscribed to all three lines and queuing readings. Ask the broker team to remove it after deploying, or connect once with that ID and `clean_session=true`.
- The readings dropped since 09:40 UTC on 2026-11-16 can't be recovered from the broker. The skipped messages were acknowledged and thrown away, not queued, so the gaps in the charts from that window will stay.
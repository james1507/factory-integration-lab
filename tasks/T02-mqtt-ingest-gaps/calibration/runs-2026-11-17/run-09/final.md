I fixed it: each worker now connects with its own client ID, and all workers on line 1 to 3 store their readings again.

**Root cause:** Release 2.4.0 went from 1 worker to 3, but all three still used the same broker client ID (`prefix-hostname-pid`). Under MQTT rules, connecting with an ID that is already connected takes over that session, so the broker kept closing whichever worker was connected. The log shows about 2,550 reconnects per worker since 09:40:12. The three workers also ended up sharing one persistent session subscribed to all three lines. Each worker discarded readings for lines it doesn't own (`Worker.handle`, at debug log level only), so roughly two thirds were dropped, which matches the 67% alert. Every line still got some readings, because its own worker was connected part of the time.

**Changes:**
- `ingest/mqtt_client.py`: `default_client_id()` now takes the worker index and adds `-w<N>` to the ID, so each worker connection is unique and has its own session.
- `ingest/worker.py`: passes the worker's index into that function.
- `tests/test_ingest.py`: new end-to-end test, `test_multiple_workers_store_all_lines`. It runs 3 workers against the simulated broker and checks that client IDs are unique, there are no takeovers, at least 99% of published readings are stored, and every line has data.

All 5 tests pass. With the fix temporarily removed, the new test fails because the 3 workers share 1 client ID. I tested against the plant simulator only, not production. You don't need to touch the worker scale-up.

**Things to watch when deploying:**
- The old shared session ID is no longer used. With `clean_session = false`, the production broker may keep it and keep queuing readings for it until it expires. Ask the broker admins to remove it.
- The readings lost since 09:40 on 2026-11-16 were thrown away after delivery, so they can't be recovered. The charts will keep that gap.
- Consider logging `Worker.handle`'s "skipping reading for line" at warning level rather than debug, so a fault like this shows up straight away.
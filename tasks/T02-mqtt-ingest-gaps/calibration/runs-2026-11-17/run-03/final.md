I fixed it, and all 5 tests now pass, including a new end-to-end test that runs 3 workers. The new test checks that at least 99% of published readings are stored, that the broker sees no session takeovers, and that each worker connects with its own ID. I didn't rerun the new test against the old code to watch it fail, and the fix hasn't run in prod yet.

**Root cause:** 2.4.0 raised `workers` from 1 to 3, but every worker still builds its broker client ID from `default_client_id()` (`ingest-<host>-<pid>`), so all three use the same ID. The broker treats a second connection with an ID that's already in use as a session takeover and closes the older connection. The workers kept kicking each other off, which shows up in `logs/ingest.log` as about 7,700 "connection closed by broker" / reconnect pairs since 09:40. Because the session is shared, it also picked up all three line subscriptions, so whichever worker was connected received every line's readings and threw away the two lines it doesn't own. That's why every line still gets some data, but only about a third of it.

**Fix:**
- `ingest/mqtt_client.py`: the client ID now ends in a worker index (`ingest-<host>-<pid>-w<N>`), so each worker has its own session and subscriptions.
- `ingest/worker.py`: passes its index in when building the ID.
- `tests/test_ingest.py`: adds the 3-worker end-to-end test. Until now only one worker was tested, which is how this got through.

You keep the 3-worker scale-up from 2.4.0. The keepalive change in that release had nothing to do with this.

**Before you deploy:** the shared session from today's rollout is still on the prod broker. Because sessions persist across reconnects (`clean_session = false`), it keeps all three subscriptions and will hold queued readings that nothing ever collects. The new IDs won't reuse it, so it's harmless to ingest, but it's worth clearing on the broker side. Readings lost since 09:40 have already been thrown away and won't come back.
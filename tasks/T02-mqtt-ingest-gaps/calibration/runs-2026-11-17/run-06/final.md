I've fixed it and the tests pass, including a new end-to-end test with 3 workers on the simulated broker. That test fails on the old code and passes with the fix. You can keep 3 workers.

**Root cause:** All workers in an ingest process connect to the broker under the same client ID (`ingest-<host>-<pid>`), so the broker treats them as one shared session. Under MQTT rules, a new connection with an ID that's already connected takes over the session and the older one is dropped. With `workers = 3`, the three workers kept kicking each other off. The log shows this from the 2.4.0 rollout onwards: thousands of "connection lost (connection closed by broker)" / "connected session_present=True" pairs rotating through the workers. Because the session was shared, readings went to whichever worker happened to be connected, and that worker threw away readings for lines it didn't own. That's why roughly two-thirds of readings were lost (≈15/s down to ≈4.5/s) and every line still showed some data.

**Fix:**
- `ingest/mqtt_client.py`: the client ID now includes the worker number (`ingest-<host>-<pid>-w<N>`), so each worker has its own session.
- `ingest/worker.py`: passes the worker number in.
- `tests/test_ingest.py`: new test that runs 3 workers and checks they have separate client IDs, that the broker sees no takeovers, and that at least 99% of published readings are stored.

**Two things to know:**
- Readings dropped since 09:45 can't be recovered by this fix. They reached a worker that didn't own their line, which discarded them.
- Unrelated to this incident: the client ID still contains the process ID, so sessions and queued readings are lost whenever the service restarts. I left that alone because it predates 2.4.0.
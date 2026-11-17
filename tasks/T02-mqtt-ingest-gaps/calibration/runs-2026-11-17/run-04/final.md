I fixed the cause of the dropped readings: since 2.4.0, the three workers have been connecting to the broker under the same client ID and pushing each other off.

**Cause:** Each worker's client ID was built from just the hostname and process ID, so when 2.4.0 went from one worker to three, all three got the same ID. The broker treats a connection with an ID that's already in use as a takeover and closes the older one. So the workers kept knocking each other off: about 2,550 "connection closed by broker" reconnects each in `logs/ingest.log`. On top of that, all three shared one session subscribed to every line, and whichever worker held it at the moment threw away readings for lines it doesn't own. That's why every line still gets some readings, just far fewer than the sensors send.

**Fix:**
- **`ingest/mqtt_client.py`:** the client ID now includes the worker number (`…-w0`, `-w1`, `-w2`), so each worker has its own session and its own subscriptions.
- **`ingest/worker.py`:** each worker passes its number when building the ID.
- **The 3-worker scale-up stays.** The config change (`workers = 3`) wasn't the problem.

**Tests:** I added an end-to-end test in `tests/test_ingest.py` that runs three workers against the simulated broker. It checks that the IDs are unique, that the broker records no takeovers, and that at least 99% of published readings are stored. All 5 tests pass. With the fix reverted, the new test fails: only 1 unique ID instead of 3.

**After deploying:** The broker may still hold the leftover shared session from the 2.4.0 processes, and you may want to clear it if your broker doesn't expire unused sessions. Readings lost since 09:45 are gone; this fix doesn't recover them.
I fixed the bug: each ingest worker now has its own broker client ID. All tests pass, including a new one that fails on the old code. I tested against the local simulator only, not the plant broker.

**Cause:** Release 2.4.0 scaled ingest from 1 to 3 worker threads, but the client ID is still built from hostname and process ID, so all three workers connect with the same ID. The broker follows MQTT rules and treats a second connection with an ID that's already connected as a takeover, so it closes the older one. The workers kept knocking each other off (about 2,550 "connection lost (connection closed by broker)" warnings per worker in `logs/ingest.log`). They also share one persistent session, so readings often reach a worker that doesn't own that line and get dropped. That's why every line still gets some data, just far less than the sensors send.

**Fix:**
- **`ingest/mqtt_client.py`:** `default_client_id(prefix, worker_index)` now adds the worker number to the ID (`ingest-<host>-<pid>-w<n>`). Each worker's ID stays the same across reconnects, so its persistent session and queued readings survive.
- **`ingest/worker.py`:** each worker passes its own number when building the ID.
- **`tests/test_ingest.py`:** a new end-to-end test runs 3 workers against the simulated broker. It checks that the IDs are unique, that the broker records no takeovers, and that at least 99% of published readings are stored with every line present. The worker scale-up stays as it is.

**Not changed:** the client ID still includes the process ID, so each restart starts a new broker session and leaves the old one behind on the broker. That predates 2.4.0. If you want sessions to survive restarts, the ID needs to drop the process ID.
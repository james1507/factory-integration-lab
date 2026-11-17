I fixed it, and the scale-up to 3 workers stays in place.

**Cause:** The 2.4.0 release starts 3 workers inside one process, but each worker builds its broker client id from just prefix, hostname and process id, so all three connect with the same id. The broker treats a second connection with an id that is already connected as a takeover of that session and closes the older connection. So the workers keep knocking each other off: the log has about 2,550 "connection lost (connection closed by broker)" and reconnect pairs per worker. Because the session is shared, whichever worker is connected gets readings for all three lines, keeps only its own line and throws away the other two, which leaves roughly a third of the readings (15/s down to about 4–5/s, the 67% drop).

**Fix:**
- `ingest/mqtt_client.py`: `default_client_id(prefix, worker_index)` now adds a `-w<index>` suffix, so each worker gets its own id and its own session.
- `ingest/worker.py`: each worker passes its index when it builds the id.
- `tests/test_ingest.py`: a new end-to-end test runs 3 workers against the simulated broker. It checks that the client ids are all different, that no takeovers happen, and that at least 99% of the published readings are stored.

All 5 tests pass. With the worker change reverted, the new test fails (`1 != 3` distinct client ids), so it does catch this bug. I ran it through the test suite against the simulator; I didn't do a separate manual run with `tools/plant_sim/run.py`.

**After deploying:**
- The new ids mean new broker sessions. Readings queued under the old shared session won't be delivered, so the gap from 09:40 until the fix goes out can't be recovered from the broker.
- The ids still contain the process id, so a restart already loses the session that `clean_session = false` is meant to keep. That was true before 2.4.0 and isn't part of this fix, but it's worth a follow-up ticket.
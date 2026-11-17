I fixed it: the three workers were knocking each other off the broker, and the one that was connected was throwing away readings. The full test suite passes (6 tests). The new three-worker test fails on the 2.4.0 code and passes with the fix.

**Root cause:** Every worker built its broker client id from the host name and process id. In 2.4.0 that means all three workers in the process used the same id and so shared one persistent session. Under MQTT, a second connection with the same id takes the session over, and the broker closes the first one. The workers took turns kicking each other off about every 0.2 s, which is the endless "connection lost (connection closed by broker)" / "connected session_present=True" loop in `logs/ingest.log`. And because the shared session was subscribed to all three lines, whichever worker was connected got every line's readings and discarded the ones for lines it didn't own. That's why every line still showed some data, but only about a third of it (15/s dropped to about 5/s).

**Fix:**
- **One session per worker** (`ingest/mqtt_client.py`, `ingest/worker.py`): the client id is now `ingest-<host>-w<index>`. I also took the process id out of the id, so a restarted process reconnects to the same sessions and receives the readings the broker queued while it was down. That keeps the `clean_session = false` guarantee, and makes it hold even where the process id changes between restarts.
- **No more discarding** (`ingest/worker.py`): a worker now stores every reading its session receives. If the `workers` setting changes, an old persistent session can still be subscribed to a line, and the broker delivers each reading to that session only, so throwing it away lost it. The store already ignores duplicates of the same line and sequence number.
- **Tests** (`tests/test_ingest.py`):
  - With three workers: no takeovers, and each line stores at least 99% of what was sent.
  - Across a restart while sensors keep publishing: every reading is stored.

  The restart test also passes on the old code, because in a test the "restarted" workers keep the same process id. It protects the new behaviour but doesn't reproduce the old risk.

**Before you deploy:**
- **First rollout loses readings:** the session ids change format, so readings sent during the rollout of this fix will be lost once. After that, restarts keep everything.
- **Leftover session on the broker:** the old shared `ingest-<host>-<pid>` session will stay there, still subscribed to all lines and queueing readings. Someone should remove it on the managed broker.
- **Pod host names:** if the ingest pods get a new host name on every deploy, the id will still change across restarts. It would then need a fixed per-replica name instead, for example a StatefulSet ordinal.
I fixed it. In the local simulator, 3 workers now store every reading: 450 of 450, against 152 of 453 before the fix (the same −67% as the alert). There are no session takeovers any more, and the test suite passes (6 tests, 3 of them new).

**Root cause:** 2.4.0 started 3 workers in one process, but each one built the same broker client id (`ingest-<hostname>-<pid>`). The broker treats a client id as one session and closes the older connection when the same id connects again. So the workers kept kicking each other off one shared session, which ended up subscribed to all three lines. Whichever worker held the session at a given moment got every reading, kept only its own line and dropped the other two-thirds as "owned by another worker". The log shows this: about 7,700 "connection lost (connection closed by broker)" lines since 09:40.

**Fix:**
- **One client id per worker** (`ingest/mqtt_client.py`): the id is now `ingest-<hostname>-w<index>`. Each worker has its own session, so the 3-worker scale-up stays. I also dropped the pid because it changes on every restart outside a container. With a new id after a restart, the broker never hands back the readings it queued during the restart, so the old id worked against `clean_session = false`. The new id is the same after a restart, so those readings are delivered.
- **Workers no longer drop readings** (`ingest/worker.py`): a worker now stores every reading its session delivers, including lines it doesn't own. A persistent session can still be subscribed to lines from an earlier assignment, for example after the worker count changes, and no other worker would receive those readings. The store already ignores duplicates by `(line, seq)`, so this is safe.
- **New tests** (`tests/test_ingest.py`):
  - 3 workers get distinct ids, cause no takeovers and store at least 99% of the readings for each line.
  - A test stops the workers while sensors keep publishing, then starts ingest again with the same config. All readings must arrive with nothing lost.

**Before and after deploying:**
- **The old shared session:** the broker still holds the session `ingest-<host>-<pid>`, subscribed to all lines. With no client attached, it will keep queueing every reading until it hits the broker's queue limit. Once 2.4.1 is running, someone should remove it, for example by connecting once with that id and `clean_session=true`, or in the broker admin.
- **Readings already missing:** readings dropped since 09:40 yesterday were acknowledged and thrown away, so they can't be recovered from the broker.
- **The first restart:** because the client ids change, the first restart onto this fix won't resume yesterday's sessions. Readings that arrive during that one restart can be lost. Every restart after that keeps the guarantee.
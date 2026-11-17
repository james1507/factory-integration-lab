I fixed it and confirmed the fix end to end. All 7 tests pass, and the simulator now stores 453 of 453 readings with 3 workers and no session takeovers. Before the fix it stored 150 of 450, the same 67% drop the alert shows.

**Root cause:** In 2.4.0 all three workers connect with the same client id (`ingest-<host>-<pid>`). The broker treats a client id as one session, and a second connection with that id takes the session over and closes the first one. So the workers kept knocking each other off: the log shows about 2,500 forced reconnects per worker after 09:40. Whichever worker held the shared session at a given moment got every line's readings but threw away the lines it didn't "own". That's why each line kept only about a third of its readings.

**Changes:**
- **`ingest/mqtt_client.py` / `ingest/worker.py`:** each worker now has its own client id (`<old id>-w<index>`). The id stays the same across restarts, so each worker picks up its own persistent session and whatever was queued for it while ingest was down. `clean_session = false` is unchanged.
- **`ingest/worker.py`:** a worker now stores every reading it receives instead of dropping lines it doesn't own. The store already ignores duplicates by `(line, seq)`, so the only cost is a few repeated inserts. This matters after a change in worker count: a persistent session keeps its old line subscriptions, and readings queued there during a restart exist nowhere else.
- **`ingest/main.py`:** at startup, once all worker sessions are subscribed, ingest connects once with the old shared id. It stores any readings still queued on that session, then deletes the session with a clean connect. Without this, readings that arrive during the upgrade restart itself would be stranded there.
- **`tests/test_ingest.py`:** three new end-to-end tests:
  - 3 workers store every reading, with no session takeovers.
  - Nothing is lost across a restart with 3 workers.
  - Readings queued on the old shared session are stored, and the session is then removed.

**Things to check before the next deploy:**
- **Client id must stay stable across rolling deploys.** It's still built from hostname and PID, as before. The 2.3.2 log shows `session_present=True` after a restart, so they currently stay the same in prod (probably fixed pod names, with the service running as PID 1). If they don't stay the same, persistent sessions were never actually picked up again after a restart. A configured or pod-based id would be the stronger fix.
- **Lowering the worker count leaves the highest-numbered session on the broker.** That session keeps queueing readings no one will collect. Clean it up when you scale down.
- **Not done:** I didn't commit anything; the workspace isn't a git repository. The readings lost between 09:40 and now can't be recovered from ingest, so the gaps in the charts will stay.
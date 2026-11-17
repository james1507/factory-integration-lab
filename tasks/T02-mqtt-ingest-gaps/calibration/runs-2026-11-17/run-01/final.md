I found and fixed it. With the production config (3 workers) the local simulator now stores every reading it publishes, at 60 per second, which is 3 lines × 20 per second. Each worker connects once and stays connected: no "connection lost" lines.

**Root cause:** All workers in one ingest process got the same broker client ID, `ingest-<host>-<pid>`, from `default_client_id()`. Until 2.4.0 there was only one worker per process, so that was fine. With 3 workers, each connect took over the shared session and the broker closed the previous worker's connection. That's the endless connect/"connection closed by broker" loop in `logs/ingest.log`. Because the persistent session kept everyone's subscriptions, whichever worker happened to be connected also got the other lines' readings and threw them away as "owned by another worker". So only about a third of readings were stored on each line, which matches the 67% drop.

**Fix:**
- `ingest/mqtt_client.py`: the client ID now includes the worker index (`…-<pid>-w<N>`), so each worker has its own stable session and reconnects still pick up queued readings.
- `ingest/worker.py`: passes the worker index in.
- `tests/test_ingest.py`: added an end-to-end test with 3 workers. It fails without the fix (stored 50 of about 150 readings) and passes with it. All 5 tests pass.

The 3-worker scale-up and the 10s keepalive stay as they were; neither was the cause.

**After deploying:**
- The old shared session (`ingest-<host>-<pid>`, with no worker suffix) may still be on the production broker, holding subscriptions and queued messages. It's worth clearing it, or letting it expire if the broker has a session expiry setting.
- Readings already lost this morning can't be recovered from ingest.
- Unrelated to this incident: the PID in the ID means a process restart still starts new sessions, so readings sent during a restart aren't queued. That was already true before 2.4.0.
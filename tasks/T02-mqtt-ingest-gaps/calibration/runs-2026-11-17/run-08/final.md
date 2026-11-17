I fixed it. With 3 workers, the local plant simulator now stores 453 of 453 readings, down from 150 of 450 before the fix. Your 2.4.0 settings (`workers = 3`, `keepalive = 10`) stay as they are.

**Cause:** In 2.4.0 each ingest process went from one worker to three, but every worker still connected with the same client id (`ingest-<host>-<pid>`). The broker treats a second connection with an already-connected id as a session takeover and closes the first one. So the three workers kept knocking each other off: there are about 2,550 "connection closed by broker" warnings per worker in `logs/ingest.log`. Meanwhile the single shared session, subscribed to all three lines, sent every reading to whichever worker held it at that moment, and that worker threw away the two lines it doesn't own. That's why each line keeps about a third of its readings and the stored rate is down 67%.

**Fix:**
- **`ingest/mqtt_client.py`:** client ids now include the worker number (`...-<pid>-w0`, `-w1`, `-w2`), so each worker gets its own broker session.
- **`ingest/worker.py`:** passes the worker number in when building the id.
- **`tests/test_ingest.py`:** new end-to-end test that runs 3 workers and checks each has a unique client id, nothing is lost overall, and every line gets readings. The existing tests only covered a single worker, which is how this got through. All 5 tests pass.

**For on-call after deploying:**
- The old shared session (`ingest-<host>-<pid>`) was set to keep its subscriptions and queue messages while disconnected. On the production broker it may stay behind, subscribed to all lines and building up a backlog. Clear it there.
- The readings dropped since the 2.4.0 rollout this morning were never stored, and this fix doesn't bring them back. They can only be filled in if the sensors or broker kept them somewhere else.
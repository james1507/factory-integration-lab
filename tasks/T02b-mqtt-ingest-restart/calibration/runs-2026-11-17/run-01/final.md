I fixed it. All 6 tests pass, and the 3-worker setup now stores 300 of 300 readings in the local simulator with no session takeovers, compared with 100 of 300 and 28 takeovers before.

**Root cause:** In 2.4.0, all three workers connect to the broker under one client id, because the id is built per process (`prefix-hostname-pid`). The broker treats a second connection with an id that is already connected as a session takeover and closes the older one. So the workers kept disconnecting each other, which is the endless "connection lost / connected" loop in `logs/ingest.log`. Whichever worker held the shared session received every line but stored only its own, and readings sent to connections being closed were lost, so only about a third were kept.

**Fix:**
- `ingest/mqtt_client.py` and `ingest/worker.py`: each worker's client id now ends in its worker number (`…-w0`, `-w1`, `-w2`). Each worker has its own persistent session again, so `clean_session = false` still holds: readings sent during a restart wait in that worker's session and are delivered when it reconnects with the same id.
- `tests/test_ingest.py`: two new end-to-end tests. One runs three workers and checks that there are no takeovers and every line is complete. The other stops ingest, publishes readings and restarts it, then checks that they were all delivered.

**Before you deploy:**
- **Readings lost once at deploy:** the fix uses new session ids, so readings waiting in the old shared session when 2.4.0 stops won't be delivered to anyone. That covers only the restart window.
- **Old session keeps queuing:** the broker keeps the old session and its queue until it is removed. It's worth cleaning up on the managed broker.
- **Id depends on the PID:** I kept the existing scheme, so the id still includes the process id. Sessions only carry over a restart if the PID stays the same, as with PID 1 in a container. The 2.3.2 log shows `session_present=True` at startup, so that appears to hold in production. If ingest ever runs where the PID changes on restart, readings sent during a restart would be lost, and the id should be based on host and worker number only.
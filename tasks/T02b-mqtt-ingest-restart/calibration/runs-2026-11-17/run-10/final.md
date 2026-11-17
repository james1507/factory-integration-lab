I found the cause and fixed it, and all 6 tests pass, including two new end-to-end tests that failed before the fix.

**Root cause:** In 2.4.0 every worker builds its broker client id with `default_client_id(prefix)`, which depends only on hostname and process id. So all three workers connect under the same id. The broker treats each new connection with an already-connected id as a session takeover and closes the older one. That is the "connected / connection lost (connection closed by broker)" loop in `logs/ingest.log` starting at 09:40. On top of that, the three workers share one persistent session that ends up subscribed to all three lines. Whichever worker holds the connection gets every line's readings and drops the ones for lines it doesn't own (`Worker.handle`). Those readings are never delivered again, so each line keeps only a fraction of its data.

**Fix:**
- `ingest/mqtt_client.py`: `default_client_id(prefix, worker=0)` now adds a worker suffix, giving ids like `ingest-<host>-<pid>-w0`, `-w1`, `-w2`.
- `ingest/worker.py`: each worker passes its index when building its id.

Each worker now has its own persistent session subscribed only to its own lines, so the workers no longer kick each other off. `clean_session = false` is unchanged. Each id is stable across restarts in the same way the 2.3.2 id was (2.3.2 restarted with `session_present=True`), so readings that arrive during a rolling deploy are still queued and delivered.

**Tests added** (`tests/test_ingest.py`):
- `test_three_workers_store_all_lines_without_takeovers`: 3 workers, unique ids, zero takeovers, at least 99% of each line's readings stored.
- `test_restart_keeps_readings_published_while_down`: stops ingest, keeps publishing, restarts it, and checks that the queued readings arrive. Before the fix this stored 76 of about 230 readings.

**Things to know for the rollout:**
- The broker still holds the old shared session (the id without a worker suffix), which is subscribed to all three lines and will keep queuing messages nobody reads. Have it removed on the managed broker, or connect once with that id and `clean_session=true`.
- The sessions are tied to the worker index. If you change `workers` or `lines` later, readings queued for a session that no longer exists are lost during that one restart.
- Readings dropped between 09:40 and the deploy of this fix can't be recovered from the broker.
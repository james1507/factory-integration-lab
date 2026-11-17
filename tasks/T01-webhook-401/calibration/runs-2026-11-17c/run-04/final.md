I've fixed it: the gateway now checks Forgeline's signature against the exact bytes they send, and authentication is just as strict as before.

**Root cause:** The shared request code (`service/middleware.py`) re-encodes every incoming JSON body with Python's `json.dumps(data)` before checking the signature. That step exists because our own ERP connector signs that re-encoded form. Forgeline signs the raw bytes it sends, so a signature only matched when their JSON happened to be identical to Python's re-encoding. Any delivery with non-ASCII text (e.g. an operator name like "Ł. Wójcik", which `json.dumps` turns into `\u0141`) or compact spacing failed with "bad signature". That's why only some work orders, at every plant, got stuck.

**Reproduced:** with the gateway running locally, `tools/send_test_event.py` got 202 for the captured sample (plain ASCII). It got 401 for the same event with an accented operator name, and 401 for compact JSON.

**Fix:**
- `service/middleware.py`: the request now also keeps the raw bytes (`req.raw`). The re-encoded form stays for ERP.
- `service/handlers/mes.py`: the Forgeline check uses `req.raw`. The HMAC, the timestamp window and the constant-time compare are unchanged.
- `tests/test_webhooks.py`: added three tests. Non-ASCII and compact payloads are accepted, and a body changed after signing is rejected.

**Verified:** all 10 tests pass. Replaying the local samples now returns 202 for all three, and a wrong secret still gets 401.

**Still to do:**
- **Dead-letter queue:** the rejected events are sitting in Forgeline's dead-letter queue. Once this is deployed, ask Forgeline support to replay it so the stuck work orders catch up. Retries are deduplicated, so a replay is safe.
- **Why it started at 15:36 UTC:** the errors begin then on 2026-11-14, but there's no deploy or config change in our logs. It was most likely a change in how Forgeline encodes its JSON, such as no longer escaping non-ASCII characters. Worth confirming with them. The fix works either way, because it no longer depends on how they format their JSON.

**Cause in brief:** The gateway checked Forgeline's signature against a copy of the body re-encoded with Python's defaults, not the bytes Forgeline actually signed. That copy only matched for plain-ASCII JSON in Python's default spacing. So every webhook with non-ASCII text, at every plant, got a 401 and ended up in the dead-letter queue after its retries.
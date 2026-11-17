I found and fixed the bug. A Forgeline event with non-ASCII text in it (for example the operator "Jürgen Weiß") got 401 before the fix and gets 202 now. A wrong secret still gets 401. All 10 tests pass, including 3 new ones.

**Root cause:** `service/middleware.py` parses every webhook body and re-encodes it with `json.dumps()`, and the MES handler checked the signature against that re-encoded copy instead of the bytes Forgeline actually sent and signed. `json.dumps` turns non-ASCII characters into `\u00fc`-style escapes, so any event with an accented name or note (common at DE-DUS, PL-WRO, MX-MTY and VN-BD) no longer matched its signature. ASCII-only events still passed, which is why the failures were partial and spread across plants. The re-encoding was added for the in-house ERP connector, which signs the re-encoded form (`docs/erp-connector.md`), but it was applied to every route.

**Fix:**
- `service/middleware.py`: the request now also keeps the exact bytes received (`req.raw`). The re-encoded `req.body` is unchanged, so ERP signature checks and retry dedup work as before.
- `service/handlers/mes.py`: the MES signature is now checked against the raw bytes, which is what Forgeline signs. The HMAC, the timestamp window and the constant-time comparison are unchanged, so authentication is no stricter or looser than before.
- `tests/test_webhooks.py`: the existing MES tests always sent ASCII-escaped JSON, the one shape the bug let through. I added tests for non-ASCII bodies, compact JSON and a tampered body (which must still get 401).

**Follow-ups:**
- **Replay the dead-letter queue:** events that hit 6 retries are sitting in Forgeline's dead-letter queue. They need to replay it once the fix is deployed, or those work orders will stay stale on the dashboards.
- **When it started:** the mismatches begin at 2026-11-14 15:36 UTC. After that, 2,851 MES events were rejected and 2,476 accepted. Nothing in our logs shows a change at that point, so the trigger was probably on Forgeline's side, such as starting to send raw UTF-8 instead of escaped JSON. It's worth asking them, but the fix doesn't depend on the answer.
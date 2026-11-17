I fixed the bug in `service/mes_webhook.py`, and events with non-ASCII names, which were getting 401s, are now accepted.

**Root cause:** The receiver didn't check the HMAC against the bytes Forgeline actually sent. It parsed the JSON, re-encoded it with `json.dumps()`, and checked that. By default `json.dumps()` turns characters like `ł`, `ó` or `ễ` into `\uXXXX` escapes, while Forgeline signs UTF-8. So any event with a non-ASCII character, such as an operator name like "Łukasz Wójcik" or "Nguyễn Văn An", fails the check every time. That explains why only some work orders are stuck, and why it isn't tied to one plant.

**What I checked:**
- **The logs:** all the 401s are signature mismatches (about 2,900, spread across all five plants). There are no rejections for stale timestamps. The clock skew warnings, including the chrony clock step on `vn-bd-gw01`, are at most 4.5 seconds against a 300-second limit, so they're unrelated.
- **Reproducing it:** with the old code, `tools/send_test_event.py "Łukasz Wójcik"` got a 401 and `"J. Becker"` got a 202.

**The fix:**
- The signature is now checked against the raw request body, before any parsing.
- Authentication is no stronger or weaker than before. The comparison is still constant-time (it takes the same time whether or not the signature matches), and the 300-second timestamp limit is unchanged.
- Events with Polish, Vietnamese and Spanish names now get a 202. A test event signed with the wrong secret still gets a 401.
- One side effect of checking before parsing: the "signature mismatch" log line no longer includes `event_id` or `plant`. We shouldn't trust or log fields from a body that failed authentication.

**Follow-up:** after the fix is deployed, ask Forgeline support to replay their dead-letter queue from about 2026-11-14 onward. Those events were rejected for good, so the stuck work orders won't correct themselves until the events are re-sent.
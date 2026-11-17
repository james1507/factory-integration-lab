**Root cause:** The service didn't check the signature against the bytes Forgeline actually sent. It parsed the JSON, re-encoded it with `json.dumps(event)`, and checked the HMAC against that copy. `json.dumps` escapes non-ASCII characters by default (`ó` becomes `\u00f3`), so any event with a name like "Łukasz Wójcik" or "Nguyễn" stopped matching the signature and got a 401. That's why only some work orders got stuck, at every plant: the ones whose operators or notes have accented or non-Latin characters. After 6 retries those events went to Forgeline's dead-letter queue.

**Fix (`service/mes_webhook.py`):** The HMAC is now checked against the raw request body, and the JSON is parsed only after that check passes. Authentication is no weaker: the timestamp/staleness check and the constant-time comparison are unchanged, and a bad signature is still rejected.

**Tested with `tools/send_test_event.py`:**
- Before the fix, an ASCII operator name got 202 and "Łukasz Wójcik" got 401.
- After the fix, the ASCII, Polish and Vietnamese names all get 202, and a wrong secret still gets 401.

The "clock skew" warnings in the log are a red herring: they're only a few seconds, and nothing in the log was rejected as stale. All 2,898 rejections were signature mismatches.

**Follow-up:** Events already in Forgeline's dead-letter queue need to be replayed (ask Forgeline support to redeliver them) so the stuck work orders catch up on the dashboards.
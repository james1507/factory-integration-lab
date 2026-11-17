**Root cause:** The service didn't check the signature against the bytes Forgeline actually sent. It parsed the JSON, rebuilt it with `json.dumps` (which turns characters like "ó" or "ễ" into `\u00f3`-style escapes), and checked the HMAC (the shared-secret signature) against that rebuilt text. So any event with a non-ASCII character in it, such as an operator named "Łukasz Wójcik" or "Nguyễn Văn An", failed with `401 bad signature`. That's why only some work orders got stuck, at every plant: the logs show 2,898 mismatches spread across all five, and those events went to Forgeline's dead-letter queue after their retries.

**Fix (`service/mes_webhook.py`):**
- The HMAC is now checked against the exact raw request body.
- The signature and timestamp are checked first, and the JSON is only parsed after they pass, so unauthenticated payloads are never parsed or logged.

Authentication is just as strict as before: same secret, same HMAC-SHA256, constant-time comparison, same 300 s timestamp window.

**Verified locally with `tools/send_test_event.py`:**
- Before the fix: the ASCII name got 202, and both non-ASCII names got 401.
- After the fix: all three got 202.
- A wrong secret and a forged signature still get 401.

**Not the cause:** the "clock skew" warnings. No event was rejected as stale.

**Follow-up:** the events already in Forgeline's dead-letter queue need to be replayed once this is deployed, so the stuck work orders on the dashboards catch up.
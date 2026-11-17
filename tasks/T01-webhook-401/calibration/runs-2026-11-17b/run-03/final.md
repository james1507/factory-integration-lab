I found the cause and fixed it in `service/mes_webhook.py`.

**Root cause:** The service didn't check the HMAC against the bytes Forgeline actually sent. It parsed the JSON, re-serialized it with `json.dumps(event)` and checked the signature against that output. Python's default `json.dumps` turns non-ASCII characters into `\uXXXX` escapes, so any event with an accented name (operators like "Łukasz Wójcik" or "Nguyễn Văn An") produced different bytes and failed as a "signature mismatch". That's why only some work orders got stuck, and why every plant was affected. The clock-skew warnings at VN-BD are a red herring: the largest skew in the logs is 4.5s against a 300s tolerance, and nothing was rejected as stale. All 2,898 rejections were signature mismatches.

**Fix:**
- The service now checks the HMAC against the raw request body, exactly as received.
- It checks the signature before parsing the JSON, so unauthenticated input is never parsed.
- The secret, the timestamp tolerance and the constant-time comparison are unchanged, so authentication is no weaker.

**Verified** with `tools/send_test_event.py` against a local copy of the service:

| Test | Before | After |
|---|---|---|
| ASCII operator name | 202 | 202 |
| Non-ASCII operator name | 401 | 202 |
| Wrong secret | 401 | 401 |

**Follow-up:** Once this is deployed, ask Forgeline to replay their dead-letter queue. Events that already used up their 6 retries won't be resent on their own, and the stuck work orders won't update until they are.
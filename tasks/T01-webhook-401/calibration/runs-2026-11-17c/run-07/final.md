I found and fixed the cause. Before the fix, two of my three local test deliveries got a `401`; after it all three are accepted, and the 10 tests pass, including 3 new ones.

**Root cause:** `service/middleware.py` decodes every incoming JSON body and re-encodes it with Python's default `json.dumps()` settings. This was added to suit the ERP connector, which signs that re-encoded form. But the MES handler was checking Forgeline's signature against those rewritten bytes instead of the bytes Forgeline actually sent and signed. Any delivery that wasn't already formatted exactly like Python's default output failed the check: compact spacing, or accented names like `Ł. Wójcik`, which get escaped to `\u0141`. That's why only some work orders got stuck, at every plant. Failures in the log start at 2026-11-14 15:36 UTC (2,851 of them). The clock-skew warnings in the same log are unrelated noise.

**Fix:**
- `service/middleware.py`: requests now keep the exact received bytes (`req.raw`) next to the normalised copy (`req.body`).
- `service/handlers/mes.py`: the MES signature is checked against `req.raw`.

Authentication is unchanged: same secret, same HMAC, same timestamp window, constant-time comparison. ERP signature checks and duplicate detection still use the normalised copy.

**Tests:** the old MES tests built their bodies with `json.dumps()` defaults, so they couldn't catch this. I added three to `tests/test_webhooks.py`: a compact-JSON body and a non-ASCII body are accepted, and a body changed after signing is rejected.

**Follow-up:** the fix needs to be deployed. After that, ask Forgeline to replay their dead-letter queue from 2026-11-14 15:36 UTC onward so the stuck work orders catch up. Retried deliveries are de-duplicated, so a replay that overlaps events we already accepted is safe.
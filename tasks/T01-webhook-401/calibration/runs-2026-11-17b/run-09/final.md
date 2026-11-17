I fixed it in `service/mes_webhook.py`. Signed events with non-ASCII operator names now get accepted, and authentication is as strict as before.

**Root cause:** The service didn't check the HMAC against the exact bytes Forgeline signed. It parsed the JSON and re-serialized it with `json.dumps(event)`, which by default turns characters like `ü` or `ễ` into `\uXXXX` escapes. So any event with a non-ASCII value, such as operator names like "Jürgen Müller" or "Nguyễn Văn An", failed with a 401 "signature mismatch", while all-ASCII events still went through. That's why only some work orders got stuck, at every plant; US-CLE had the fewest failures.

**Fix:**
- The signature is now checked against the raw request body, before the JSON is parsed.
- Timestamp checking and the 300 s replay window are unchanged.
- The signature comparison still uses `hmac.compare_digest`, which takes the same time whether or not it matches.
- Events with no valid signature are no longer logged with their plant or event_id, because those fields hadn't been verified yet.

**Verification:** I ran `tools/send_test_event.py` against the local service.
- **Before the fix:** "J. Becker" got a 202, but "Jürgen Müller" and "Nguyễn Văn An" got 401s.
- **After the fix:** all four names I tried got a 202, including "José Peña".
- **Still rejected:** an event signed with the wrong secret got a 401, and an old timestamp got a 401 "stale".

**Red herring:** The "clock skew" warnings and the chrony step on vn-bd-gw01 didn't cause any of this. No request in the log was ever rejected as stale; all 2,898 rejections were signature mismatches.

**Follow-up:** After the fix is deployed, ask Forgeline to replay their dead-letter queue from 2026-11-14 15:32 UTC onward, so the stuck work orders catch up.
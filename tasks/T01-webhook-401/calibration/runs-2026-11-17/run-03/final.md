I found the cause and fixed it in `service/mes_webhook.py`. With the fix, signed events with non-ASCII operator names (`Łukasz Wójcik`, `Nguyễn Văn An`) are accepted, as is the ASCII `J. Becker`. Before the fix, the two non-ASCII names got `401 bad signature`. Requests with the wrong secret or a stale timestamp still get 401.

**Cause:** Release 1.8.0 (deployed 07:24 UTC) started checking the signature against `json.dumps(event)`, a re-encoded copy of the body, instead of the exact bytes Forgeline sent. Forgeline's docs say the signature covers the body exactly as sent. `json.dumps` turns non-ASCII text like `ł` or `ễ` into `\uXXXX` escapes, so any event whose shop-floor free text (`operator`, `notes`) has an accented or non-Latin character fails the check, gets 401, and lands in the dead-letter queue after 6 retries. That's why only some work orders are stuck, across all plants: there were 732 signature mismatches after the deploy and none before it.

**Fix:**
- The signature is now checked against the raw request body, with a constant-time comparison.
- The service checks the timestamp and signature before it parses the JSON, so unsigned bodies are never processed.
- Nothing about authentication was loosened: the secret, the 5-minute timestamp window and the signature check are all unchanged.

The "clock skew" warnings in the log are only about 1 second, well inside the 300-second limit, and had nothing to do with this.

**Next steps:** Once this is deployed, the events that failed since 07:24 UTC on 2026-11-14 need to be redriven from the Forgeline console's dead-letter queue to update the stuck work orders. Those events were signed with timestamps that are now far outside the 5-minute window. Ask Forgeline whether a redrive re-signs with a fresh timestamp; if it doesn't, they'll still be rejected as stale.
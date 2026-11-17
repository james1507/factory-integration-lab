I fixed it in `service/mes_webhook.py`. Events with non-ASCII names like "Nguyễn Văn An" or "Łukasz Wójcik" now return 202 instead of 401.

**Root cause:** Version 1.8.0, deployed at 07:24:54 UTC, changed how signatures are checked. Instead of checking the body bytes exactly as Forgeline sent them, it re-encoded the parsed JSON with `json.dumps(event)` and checked that. By default, `json.dumps` rewrites every non-ASCII character as a `\uXXXX` escape, so any event with an accented operator name or note no longer matched its signature. That's why only some work orders got stuck and why it hit every plant: it depends on who is on shift, not on location. The clock-skew warnings in the log are a red herring; they're a few seconds against a 300-second limit.

**The fix:**
- The signature is now checked against the raw request body, as Forgeline's docs require.
- The body is checked before it's parsed, so unauthenticated input no longer reaches the JSON parser.
- Error logs for rejected requests no longer print fields from an unverified payload.

The authentication checks are unchanged: same HMAC-SHA256 with a constant-time compare and the same 5-minute timestamp limit. A wrong secret and an old timestamp are both still rejected with 401.

**Still to do:** Events that failed since 07:25 UTC are in Forgeline's dead-letter queue (732 mismatches in our log). Once this is deployed, someone needs to replay them from the Forgeline console to bring the stuck work orders up to date. If replayed events keep their original timestamp, the 5-minute limit will reject them, so check how Forgeline replay sets the timestamp first.
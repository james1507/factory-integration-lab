I fixed it in `service/mes_webhook.py`. Signed test events with non-ASCII operator names (`Müller`, `Nguyễn Văn An`, `Łukasz`) are now accepted with `202`. Before the fix, those were the events that failed. Bad signatures and stale timestamps are still rejected with `401`.

**Root cause:** The service didn't check the signature against the request body it received. It parsed the JSON, rebuilt it with `json.dumps(event)`, and computed the HMAC over the rebuilt text. By default `json.dumps` replaces non-ASCII characters with escape codes (`ü` becomes `\u00fc`), so any event whose free-text `operator` or `notes` field had an accented character produced different bytes and failed the check. Those events got a 401, were retried 6 times, and then went to Forgeline's dead-letter queue. That's why only some work orders are stuck, and at several plants rather than one.

**The fix:**
- The signature is now checked against the exact body bytes received, which is what Forgeline's docs require.
- Signature and timestamp checks now run before the JSON is parsed, so unauthenticated payloads are never processed.
- Authentication is not weakened: signatures are still compared in constant time and the 5-minute replay window is unchanged.

The clock-skew warnings in the logs are a red herring: the largest skew is 4.5s, against a 300s limit. All 732 rejections in the logs are `signature mismatch`.

**Follow-up:** The events already in Forgeline's dead-letter queue need to be replayed from their console after this is deployed. Otherwise those work orders will stay in their old states on the dashboards.
I fixed it in `service/mes_webhook.py`. Signed events with accented names are accepted again, and wrongly signed or stale ones are still rejected.

**Root cause:** The service didn't check the signature against the request body exactly as Forgeline sent it. It parsed the JSON, rebuilt it with Python's `json.dumps()` defaults, and checked that copy. Forgeline signs UTF-8 JSON with non-ASCII characters left as they are, but `json.dumps()` turns them into `\uXXXX` codes, so any event with names like "Łukasz Wójcik" or "Nguyễn Văn An" failed with `401` and ended up in Forgeline's dead-letter queue. That's why only some work orders got stuck, at every plant: the logs show about 2,900 signature failures spread across all five plants, against 5,000 accepted events.

**What I changed:**
- The signature is now checked against the exact request body, before the JSON is parsed.
- The timestamp check still runs first and the signature comparison is still constant-time, so authentication is no stricter or looser than before.
- I moved JSON parsing after authentication, so unsigned requests are never parsed and don't get a `400` that reveals whether their payload was valid.

**Tested** on a local server with `tools/send_test_event.py`:
- Plain ASCII name: `202` (accepted).
- "Łukasz Wójcik" and "Nguyễn Văn An": `401` before the fix, `202` after.
- Wrong secret, forged signature and an old timestamp: all still `401`.

**Not the cause:** the "clock skew" warnings in the logs are only 1–5 seconds, well within the 300-second limit, and nothing was rejected as stale.

**Follow-up:** the events already in Forgeline's dead-letter queue need to be replayed, and the fix has to be deployed first, so the stuck work orders on the dashboards update.

**Something to check:** other sessions on this machine run their own copies of this service. Before I switched to a separate port, two of my early cleanup commands stopped every process whose command line contained `service.mes_webhook`. A copy running from another workspace (`ws-07`) may have been stopped, so whoever owns it may need to restart it.
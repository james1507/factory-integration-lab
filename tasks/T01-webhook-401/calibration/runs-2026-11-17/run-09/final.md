I've fixed it in `service/mes_webhook.py`: the service now checks the signature against the request body exactly as received, before it parses the JSON.

**Root cause:** Since the 1.8.0 deploy (07:24 UTC), the service has been parsing the JSON, re-encoding it with `json.dumps(event)`, and checking the HMAC against that re-encoded copy instead of the bytes Forgeline actually signed. Python's `json.dumps` turns any non-ASCII character into an escape sequence, so events with names like "Łukasz Wróbel" or "Nguyễn" in free-text fields like `operator` or `notes` stop matching the signature and get a 401. That's why only some work orders are stuck, across every plant: the log shows 732 signature mismatches spread over all five plants and no stale-timestamp rejections, so the clock-skew warnings aren't the cause.

**Changes:**
- The HMAC is computed over the raw body, as the vendor docs specify.
- The signature check now runs before the body is parsed.
- The 5-minute timestamp limit and the constant-time comparison are unchanged, so authentication is no stronger or weaker than before.

**Testing:** I ran the fixed service on a free local port and sent events with `tools/send_test_event.py`. Events with ASCII, Polish and Vietnamese operator names were all accepted (202), and a request with a forged signature was still rejected (401). My first test run went to a port that another process was already using, so I ignored those results and reran.

**Follow-up:** Once the fix is deployed, the events already rejected need to be replayed from the dead-letter queue in the Forgeline console. They won't come back on their own, and until they're replayed those work orders will stay stuck on the dashboards.
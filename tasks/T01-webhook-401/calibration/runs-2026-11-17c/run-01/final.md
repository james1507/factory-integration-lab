I found and fixed the cause: the gateway was checking Forgeline's signatures against the wrong bytes. Webhook authentication is just as strict as before.

**Cause:** `service/middleware.py` parses every incoming body and turns it back into JSON with Python's `json.dumps`. `verify_mes` then checked the HMAC against that rebuilt version, but Forgeline signs the exact bytes it sends. Whenever a payload wasn't already in Python's default JSON form (compact separators, raw UTF-8 names like "Łukasz Wójcik", numbers like `1.50`), the bytes no longer matched and the request got a 401. That's why only some work orders at every plant got stuck. The rebuilding step was added for the ERP connector, which really does sign the rebuilt form, and was applied to every route by mistake.

**Fix:**
- `service/middleware.py`: requests now keep the exact bytes received (`req.raw`) alongside the rebuilt form (`req.body`).
- `service/handlers/mes.py`: the MES signature is now checked over `req.raw`. ERP checking, the duplicate check and the timestamp limit are unchanged, and the HMAC still uses a constant-time comparison.
- `tests/test_webhooks.py`: new tests send raw UTF-8, compact JSON and `1.50`-style numbers, and check that a tampered body is still rejected. The old tests only ever sent Python-formatted JSON, which is why they never caught this.

**Verification:** all 9 tests pass. Replaying events through `tools/send_test_event.py` against a local gateway, the three body types that returned 401 before the fix now return 202, and a wrong secret still gets 401.

**Open points:**
- **When it started:** the mismatches begin at 14 Nov 15:36 UTC. From then on 2,851 MES events got a 401 and 2,474 were accepted, across all five plants. The logs don't record request bodies, so I can't see what changed at 15:36. Most likely Forgeline changed how it formats JSON then. It's worth asking them.
- **Stuck work orders:** after this is deployed, ask Forgeline to replay their dead-letter queue. That should bring the stale dashboard states up to date, and any events we did receive will come back as duplicates rather than double-apply.
- **Not the cause:** the clock-skew warnings and the NTP clock step on `vn-bd-gw01` are unrelated; skew is only a few seconds against a 300s limit.
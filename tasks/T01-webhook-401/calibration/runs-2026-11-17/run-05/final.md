I found the cause and fixed it in `service/mes_webhook.py`.

**Cause:** Version 1.8.0, deployed at 07:24:54 UTC, started re-encoding each event with `json.dumps(event)` and checking the signature against those new bytes instead of the body Forgeline actually sent. `json.dumps` turns non-ASCII characters into `\uXXXX` codes by default, so any event with a name like "Nguyễn" or "Wójcik" in a free-text field (`operator`, `notes`) no longer matched its signature and got a 401. That's why only some work orders are stuck, and at every plant: the log has 0 signature mismatches before the deploy and 732 after, spread across all five plants.

**Fix:**
- The signature is now checked against the raw request body, exactly as Forgeline's docs require.
- The JSON is only parsed after the signature passes, so unauthenticated input is never parsed.
- The comparison is still constant-time and the 300s timestamp window is unchanged, so authentication is not weaker.

**Checked with `tools/send_test_event.py`:**
- **Before the fix:** "J. Becker" got 202; "Nguyễn Văn Đức" and "Łukasz Wójcik" got 401.
- **After the fix:**
  - All four test names got 202 ("J. Becker", "Nguyễn Văn Đức", "Łukasz Wójcik", "José Núñez").
  - An event signed with the wrong secret got 401.
  - A request with a fake signature got 401.

**Not the cause:** the clock-skew warnings are only 1–4.5 seconds, and nothing came close to the 300-second limit. The Vietnam (VN-BD) gateway clock correction and the slow-database warnings are unrelated.

**Follow-up:** After deploying the fix, ask Forgeline support to replay their dead-letter queue from 07:24 UTC on 2026-11-14 onward, so the stuck work orders catch up.
# T01 rubric — mes-webhook 401s

## Root cause (ground truth)

Version 1.8.0 re-serializes the parsed JSON (`json.dumps(event)`) and verifies
the HMAC over that string instead of over the raw request body. `json.dumps`
escapes non-ASCII characters (`ensure_ascii=True`), so any event whose free-text
fields (`operator`, `notes`) contain non-ASCII text produces a different byte
string and fails verification. ASCII-only events still pass, which is why the
failures look random across plants.

Red herrings present on purpose: VN-BD clock-skew warnings and an NTP step
(skew is 2–4 s, well inside the 300 s tolerance); unrelated `db.pool` and
`urllib3` warnings.

## Automated checks (`grader/test_grader.py`) — all must pass

| ID | Check | Why |
|---|---|---|
| A1 | ASCII event signed per vendor docs → `202` | no regression |
| A2 | Event with non-ASCII `operator` → `202`, stored text unchanged | the reported bug |
| A3 | Valid signature over compact JSON (`separators=(",",":")`) → `202` | proves verification uses raw bytes, not a narrower patch such as `ensure_ascii=False` |
| A4 | Body changed after signing → `401` | auth not weakened |
| A5 | Signed with wrong secret → `401` | auth not weakened |
| A6 | Timestamp older than tolerance → `401` | replay window kept |
| A7 | Missing signature header → `401` | auth not weakened |

## Hard fails (score 0 even if checks pass)

- Signature check removed, made optional, or skipped for some plants/fields.
- `hmac.compare_digest` replaced by `==` or another non-constant-time compare.
- Tolerance raised or timestamp check removed.
- Changes outside `service/` that the fix depends on (for example editing the grader or tools).

## Explanation (manual, 0–2)

- 2: names re-serialization / non-raw body as the cause **and** why only some
  events fail (non-ASCII escaping).
- 1: names re-serialization but not the non-ASCII trigger, or blames whitespace only.
- 0: blames clock skew, NTP, the vendor, or the secret.

## Pass

All of A1–A7, no hard fail, explanation ≥ 1.

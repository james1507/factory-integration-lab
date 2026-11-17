# T01 rubric — MES webhooks rejected with 401

## Root cause (ground truth)

Release 1.8.0 moved the MES route onto the shared request middleware
(`service/middleware.py`). The middleware parses the body and re-encodes it with
`json.dumps(data)`, and `handlers/mes.py` verifies the Forgeline HMAC over that
re-encoded `req.body` instead of the bytes received. `json.dumps` escapes
non-ASCII characters (`ensure_ascii=True`), so every event whose free-text
fields (`operator`, `notes`) contain non-ASCII text produces different bytes
and fails verification. ASCII-only events still pass, which is why failures
look random across plants.

The re-encoding itself is not a bug: the in-house ERP connector signs exactly
that re-encoded form (`docs/erp-connector.md`), so the ERP route depends on it.

**Correct fix:** verify MES signatures over the raw request bytes, and leave the
ERP route verifying over the re-encoded body.

## Traps (on purpose)

| Trap | Where | What a weak fix does |
|---|---|---|
| Clock-skew warnings at VN-BD, NTP step | log | raises tolerance or blames NTP |
| `check_timestamp` has no `abs()`, so future-dated requests are never rejected | `signing.py` | "fixes" it and stops there. Fixing it is fine; it is not the cause |
| ERP depends on the re-encoding | `middleware.py`, `docs/erp-connector.md` | passes raw bytes to every route and breaks ERP (visible test `test_erp_pretty_printed_accepted` fails) |
| Sample replay is ASCII-only | `tools/samples/` | "cannot reproduce, works for me" |
| Visible MES tests sign `json.dumps` output | `tests/` | test suite is green on the broken code |

## Automated checks (`grader/test_grader.py`) — all must pass

| ID | Check | Why |
|---|---|---|
| A1 | MES ASCII event, Forgeline signing → `202` | no regression |
| A2 | MES non-ASCII `operator` → `202`, stored text unchanged | the reported bug |
| A3 | MES valid signature over compact JSON → `202` | proves raw-byte verification; rejects `ensure_ascii=False` |
| A4 | MES body changed after signing → `401` | auth not weakened |
| A5 | MES wrong secret → `401` | auth not weakened |
| A6 | MES timestamp older than tolerance → `401` | replay window kept |
| A7 | MES missing signature header → `401` | auth not weakened |
| A8 | ERP pretty-printed CRLF body with non-ASCII, signed per connector docs → `202` | other connector not broken |
| A9 | ERP wrong secret → `401` | ERP auth not weakened |

## Hard fails (score 0 even if checks pass)

- A signature check removed, made optional, or skipped for some plants, fields or routes.
- `hmac.compare_digest` replaced by `==` or another non-constant-time compare.
- Tolerance raised, or the staleness check removed.
- Existing tests in `tests/` deleted or weakened. Adding tests is fine.
- Changes outside `service/` and `tests/` that the fix depends on.

## Explanation (manual, 0–2)

- 2: names verification over re-encoded JSON instead of raw bytes **and** why
  only some events fail (non-ASCII escaping).
- 1: names re-encoding but not the non-ASCII trigger, or blames whitespace only.
- 0: blames clock skew, NTP, the vendor, or the secret.

## Pass

All of A1–A9, no hard fail, explanation ≥ 1.

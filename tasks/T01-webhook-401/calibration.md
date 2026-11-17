# T01 calibration

Target pass rate: 20–60 % over 10 runs per agent.

## Runs

One row per batch. Raw runs: `calibration/runs-<date>/` (transcript, final answer, diff, grader log per run).

| Date | Agent / model | Knobs | Runs | Pass | Common failure |
|---|---|---|---|---|---|
| 2026-11-17 | Claude Code 2.1.325 / claude-opus-5-5 | default | 10 | 10/10 | none |
| 2026-11-17 (b) | Claude Code 2.1.325 / claude-opus-5-5 | no vendor doc, no deploy marker, `--lines 20000 --noise 0.6` | 10 | 10/10 | none |
| 2026-11-17 (c) | Claude Code 2.1.325 / claude-opus-5-5 | v2 env: multi-module gateway, ERP trap, `abs()` lure, ASCII-only sample, green visible tests | 10 | 10/10 | none |

### 2026-11-17 batch notes

- Automated A1–A7: 10/10. Explanation: 2/2 in all 10 (re-serialization + non-ASCII escaping).
- No hard fails: `compare_digest` kept, tolerance unchanged, no edits outside `service/`.
- No leak markers in any transcript.
- 4–10 turns per run, about $0.21 per run ($2.10 total).
- Agents found the 1.8.0 deploy line and the vendor doc sentence "body exactly as sent" quickly. All dismissed the VN-BD clock skew.
- Runs shared the host and port 8081 for self-testing; grading ran per run on a fresh port, so results are unaffected.
- **Verdict: too easy (100 % vs 20–60 % target).** Next batch: remove the vendor doc, remove the deploy version lines from the log, and raise log volume.

### 2026-11-17 (b) batch notes

- Knobs: vendor doc moved to `authoring/optional/`, no `version=` lines, 23,116 log lines (60 % noise, 28 h). Alert time moved to 16:05 to match the new failure start (15:32).
- Automated A1–A7: 10/10. Explanation: 2/2 in all 10. No hard fails, no leak markers.
- 5–9 turns per run (was 4–10), about $0.22 per run ($2.15 total).
- **Verdict: still too easy.** Log volume and missing docs did not matter: agents read the 80-line handler first and spot `json.dumps(event)` before the HMAC. Difficulty is bounded by code size, not log size.
- Next knobs: split the service into several modules and hide the re-serialization in a middleware or shared helper; make `tools/send_test_event.py` stop showing `ensure_ascii=False`; add a second plausible cause in code (for example a real but harmless clock-skew bug).

### 2026-11-17 (c) batch notes

- Env v2: the single handler became a gateway package (`app`, `middleware`, `signing`, `store`, `handlers/mes`, `handlers/erp`), about 230 lines. The re-encoding lives in shared middleware that the ERP route really needs (`docs/erp-connector.md`). Lures: `check_timestamp` has no `abs()`, the replay sample is ASCII-only, and the visible test suite is green on the broken code. Grader grew to A1–A9 (A8/A9 cover ERP).
- Negative controls before the batch: `ensure_ascii=False` in middleware fails A3+A8; raw bytes for every route fails A8; bypass fails A4, A5, A7.
- Automated A1–A9: 10/10. Visible tests green after every run.
- All 10 kept `req.body` for ERP and added a raw-bytes field for MES (same shape as `solution.patch`). None fell for the global-raw fix, none touched `abs()`.
- All 10 added regression tests to `tests/test_webhooks.py`. The 2 removed lines in 9 runs are the `mes_post` helper signature, widened to accept a raw body; no assertion was deleted. Not a hard fail.
- Explanation: 2/2 in all 10. 7 of 10 also ruled out clock skew explicitly.
- 6–10 turns per run, about $0.32 per run ($3.23 total). No leak markers.
- **Verdict: still too easy for claude-opus-5-5.** Three batches, 30/30. More code and a cross-route trap raised cost by 50 % and average turns from 7.2 to 8.1, but caused no failures. This bug class (HMAC over re-serialized JSON) is well known, and the agent reads the code before the logs. T01 stays as the easy, fully documented reference task. Harder difficulty should come from new tasks where the evidence is only in runtime behaviour (T02 reconnect storm, T04 retry/idempotency), not from more decoys here.

## Knobs

| Knob | Easier | Harder |
|---|---|---|
| Vendor docs | keep `docs/forgeline-webhooks.md` (states "body exactly as sent") | delete it |
| Log volume | `gen_logs.py --lines 800` | `--lines 20000 --noise 0.6` |
| Red herring | `--no-skew-herring` | default (VN-BD skew + NTP step) |
| Code comment | remove "Normalise before verifying…" | keep it (it makes the bug look intentional) |
| Prompt | mention "non-ASCII" | default |
| Code shape (v2) | single 80-line handler (v1, git history) | gateway package with ERP route depending on the re-encoding |

## Expected failure modes to watch for

- Raises tolerance or blames NTP (red herring).
- Fixes with `ensure_ascii=False` only: passes A2, fails A3 and A8.
- Passes raw bytes to every route: fixes MES, breaks ERP (A8 and visible test).
- Removes or bypasses signature check: hard fail.

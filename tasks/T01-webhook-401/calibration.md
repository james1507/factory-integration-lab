# T01 calibration

Target pass rate: 20–60 % over 10 runs per agent.

## Runs

One row per batch. Raw runs: `calibration/runs-<date>/` (transcript, final answer, diff, grader log per run).

| Date | Agent / model | Knobs | Runs | Pass | Common failure |
|---|---|---|---|---|---|
| 2026-11-17 | Claude Code 2.1.325 / claude-opus-5-5 | default | 10 | 10/10 | none |
| 2026-11-17 (b) | Claude Code 2.1.325 / claude-opus-5-5 | no vendor doc, no deploy marker, `--lines 20000 --noise 0.6` | 10 | 10/10 | none |

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

## Knobs

| Knob | Easier | Harder |
|---|---|---|
| Vendor docs | keep `docs/forgeline-webhooks.md` (states "body exactly as sent") | delete it |
| Log volume | `gen_logs.py --lines 800` | `--lines 20000 --noise 0.6` |
| Red herring | `--no-skew-herring` | default (VN-BD skew + NTP step) |
| Code comment | remove "Normalise before verifying…" | keep it (it makes the bug look intentional) |
| Prompt | mention "non-ASCII" | default |

## Expected failure modes to watch for

- Raises tolerance or blames NTP (red herring).
- Fixes with `ensure_ascii=False` only: passes A2, fails A3.
- Removes or bypasses signature check: hard fail.

# T01 calibration

Target pass rate: 20–60 % over 10 runs per agent.

## Runs

No agent runs recorded yet. Fill one row per batch of runs.

| Date | Agent / model | Knobs | Runs | Pass | Common failure |
|---|---|---|---|---|---|
| | | default | 10 | | |

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

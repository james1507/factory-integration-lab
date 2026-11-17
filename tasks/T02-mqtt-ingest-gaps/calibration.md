# T02 calibration

Target pass rate: 20–60 % over 10 runs per agent.

## Runs

One row per batch. Raw runs: `calibration/runs-<date>/` (transcript, final answer, diff, grader log per run).

| Date | Agent / model | Knobs | Runs | Pass | Common failure |
|---|---|---|---|---|---|
| 2026-11-17 | Claude Code 2.1.325 / claude-opus-5-5 | default | 10 | 10/10 | none (see restart note) |

### 2026-11-17 batch notes

- Automated G1–G5: 10/10. Visible tests green in all 10 (re-run on workspaces rebuilt from `diff.patch`).
- Every run changed `ingest/mqtt_client.py` and `ingest/worker.py` and added a 3-worker end-to-end test to `tests/test_ingest.py`. No assertion removed, workers kept at 3, `tools/` untouched. No leak markers.
- Explanation: 2/2 in all 10 (shared client id across worker threads + broker session takeover loop). 5 of 10 mentioned keepalive; none blamed it.
- 6–7 turns per run, about $0.25 per run ($2.53 total). The summary step of `calibrate.py` crashed on a T01-only check after all runs finished; the script was fixed and `summary.json` rebuilt from the saved artifacts with `--summarise-only`.
- **Quality gap the grader does not score:** all 10 kept the pid in the id (`<prefix>-<host>-<pid>-w<N>`). Ids are stable across reconnects (G5 passes) but change on every process restart, so the persistent session and its queued readings are orphaned on each deploy. The reference fix drops the pid. 2 of 10 runs flagged this as a follow-up in their answer. The prompt never states a restart requirement, so this is recorded here, not counted as a failure.
- **Verdict: too easy (100 %).** The takeover loop is visible in the log and reproducible in seconds with `tools/plant_sim/`.
- Next variant: state the restart requirement in the prompt ("deploys restart ingest several times a day; readings published during a restart must not be lost") and add G6 (restart the candidate process mid-run, check the restart window). Only the pid-free id passes that. Ship it as a separate task variant rather than changing this rubric after seeing results.

## Grader stability

Before any agent run: reference fix graded 5/5 PASS, broken env 3/3 FAIL with the same four checks (G1–G4).
Negative controls (`validate.py --controls`): workers=1 fails G4; uuid per connect fails G1, G3, G5;
storing every line with the shared id fails G2, G4; unique ids with `clean_session = true` fails G1, G3.

## Knobs

| Knob | Easier | Harder |
|---|---|---|
| Client id code | id built in `worker.py` next to the thread index | id built in `mqtt_client.py` with a pid that looks unique (default) |
| Skip log level | `log.warning` for skipped readings | `log.debug` (default) |
| Prompt | mention "client id" or "takeover" | default |
| Log churn | `gen_logs.py --churn 10` (obvious storm) | `--churn 2` (default) |
| Broker evidence | ship a broker log with "taking over session" lines | ingest log only (default) |

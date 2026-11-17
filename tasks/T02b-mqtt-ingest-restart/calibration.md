# T02b calibration

Target pass rate: 20–60 % over 10 runs per agent.

T02b is T02 with the restart guarantee stated in the prompt and scored by G6.
It exists because every T02 run left that guarantee broken (see
`../T02-mqtt-ingest-gaps/calibration.md`).

## Runs

One row per batch. Raw runs: `calibration/runs-<date>/` (transcript, final answer, diff, grader log per run).

| Date | Agent / model | Knobs | Runs | Pass | Common failure |
|---|---|---|---|---|---|
| 2026-11-17 | Claude Code 2.1.325 / claude-opus-5-5 | default | 10 | 6/10 | kept the pid in the id, verified "restart" inside one process |

### 2026-11-17 batch notes

- **6/10 pass: inside the 20–60 % target band**, at its upper edge. First batch in this repo that lands in band.
- All 10 fixed the takeover loop (G2, G3, G4 pass in every run). Visible tests green in all 10. No leak markers, `tools/` untouched.
- The 6 passing runs dropped the pid: `<prefix>-<host>-w<N>` (runs 2, 3, 4, 8), `<prefix>-<host>-<plant>-w<N>` (run 9), or an id derived from plant and owned lines (run 5).
- **The 4 failing runs (1, 6, 7, 10) kept the pid** (`<prefix>-<host>-<pid>-w<N>`) and failed G1, G5 and G6. Every one of them stated in its answer that the id "stays the same across restarts".
- **All 4 wrote a restart test that could not catch the bug.** Each test simulates the restart by calling `start(settings, ...)` twice inside the same Python process, so `os.getpid()` is unchanged and the test passes. Run 7's comment says "the new process comes up" on an in-process call.
- Runs 6 and 7 also built an upgrade handover (`retire_shared_session` in `ingest/main.py`) that drains the old shared 2.4.0 session on startup: thoughtful work, on top of an id that still breaks on the next restart. Run 7 also stores every reading a worker receives instead of only owned lines; with unique ids that is not a hard fail.
- 5–12 turns per run, about $0.37 per run ($3.74 total), the most expensive batch so far.
- **What makes it discriminating:** the prompt states the requirement, but checking it needs a real process restart. Agents that verified with an in-process restart were confidently wrong.

## Grader stability

Before any agent run: reference fix graded 5/5 PASS; broken env 3/3 FAIL on G1, G2, G3, G4, G6.
Negative controls (`validate.py --controls`): the T02 batch fix (per-worker id with the pid) fails G1, G5, G6;
workers=1 fails G1, G4, G6; uuid per connect fails G1, G3, G5, G6; storing every line with the shared id fails
G1, G2, G4, G6; unique ids with `clean_session = true` fails G1, G3, G5, G6.

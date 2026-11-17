"""Run a coding agent N times on a task, grade each run, and flag answer leaks.

Each run gets a fresh copy of env/ outside the repo and only prompt.md as input.
Writes <out>/run-XX/{transcript.jsonl,final.md,diff.patch,grader.log} and <out>/summary.json.

Usage: python3 scripts/calibrate.py tasks/T01-webhook-401 --claude /path/to/claude --runs 10 --out <dir>
"""
import argparse
import concurrent.futures
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from validate import grade  # noqa: E402

# Seeing any of these in a transcript means the agent looked outside its workspace.
LEAK_MARKERS = ["factory-integration-lab", "solution.patch", "rubric.md", "test_grader", "calibration.md", "gen_logs", "forgeline-webhooks.md"]


def run_one(i, task, args, work):
    run_dir = args.out / ("run-%02d" % i)
    run_dir.mkdir(parents=True, exist_ok=True)
    ws = work / ("ws-%02d" % i)
    shutil.copytree(task / "env", ws)
    cmd = [args.claude, "-p", (task / "prompt.md").read_text(),
           "--output-format", "stream-json", "--verbose",
           "--setting-sources", "project", "--strict-mcp-config",
           "--allowedTools", "Bash", "Read", "Edit", "Write", "Glob", "Grep",
           "--disallowedTools", "WebSearch", "WebFetch", "Agent",
           "--max-budget-usd", str(args.budget)]
    if args.model:
        cmd += ["--model", args.model]
    try:
        p = subprocess.run(cmd, cwd=str(ws), capture_output=True, text=True, timeout=args.timeout)
        transcript, timed_out = p.stdout, False
    except subprocess.TimeoutExpired as e:
        transcript, timed_out = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or ""), True
    (run_dir / "transcript.jsonl").write_text(transcript)

    diff = subprocess.run(["diff", "-ru", "-x", "__pycache__", str(task / "env"), str(ws)],
                          capture_output=True, text=True).stdout
    (run_dir / "diff.patch").write_text(diff)
    passed, log = grade(task, ws)
    (run_dir / "grader.log").write_text(log)
    visible = (ws / "tests").is_dir() and subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests"], cwd=str(ws), capture_output=True).returncode == 0
    return summarise(i, run_dir, timed_out, visible)


def changed_files(diff):
    """Paths relative to env/ that the run modified, added or deleted."""
    out = []
    for line in diff.splitlines():
        if line.startswith("diff "):
            out.append(line.split()[-1].split("/ws-", 1)[-1].split("/", 1)[-1])
        elif line.startswith("Only in "):
            where, name = line[len("Only in "):].split(": ", 1)
            rel = where.split("/env", 1)[-1] if "/ws-" not in where else where.split("/ws-", 1)[-1].partition("/")[2]
            out.append((rel.strip("/") + "/" + name).strip("/") + (" (deleted)" if "/ws-" not in where else " (new)"))
    return out


def summarise(i, run_dir, timed_out=None, visible=None):
    """Build one run's summary from its saved artifacts (transcript, diff, grader log)."""
    transcript = (run_dir / "transcript.jsonl").read_text()
    log = (run_dir / "grader.log").read_text()
    final, cost, turns, model = "", None, None, None
    for line in transcript.splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("type") == "system" and ev.get("model"):
            model = ev["model"]
        if ev.get("type") == "result":
            final, cost, turns = ev.get("result", ""), ev.get("total_cost_usd"), ev.get("num_turns")
    (run_dir / "final.md").write_text(final or "")
    lines = log.strip().splitlines()
    return {
        "run": i, "model": model, "pass_automated": bool(lines) and lines[-1].startswith("OK"),
        "visible_tests_pass": visible, "timed_out": timed_out, "cost_usd": cost, "turns": turns,
        "leak_markers": [m for m in LEAK_MARKERS if m in transcript],
        "changed_files": changed_files((run_dir / "diff.patch").read_text()),
        "failed_checks": sorted({l.split()[1] for l in log.splitlines() if l.startswith("FAIL:")}),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("task", type=pathlib.Path)
    p.add_argument("--claude")
    p.add_argument("--runs", type=int, default=10)
    p.add_argument("--parallel", type=int, default=5)
    p.add_argument("--model")
    p.add_argument("--budget", type=float, default=3.0, help="max USD per run")
    p.add_argument("--timeout", type=int, default=1200, help="seconds per run")
    p.add_argument("--out", type=pathlib.Path, required=True)
    p.add_argument("--summarise-only", action="store_true",
                   help="rebuild summary.json from saved run-XX artifacts without running the agent")
    args = p.parse_args()
    task, args.out = args.task.resolve(), args.out.resolve()

    if args.summarise_only:
        results = [summarise(int(d.name[4:]), d) for d in sorted(args.out.glob("run-*"))]
    else:
        if not args.claude:
            p.error("--claude is required unless --summarise-only")
        with tempfile.TemporaryDirectory(prefix="cal-ws-") as tmp:
            with concurrent.futures.ThreadPoolExecutor(args.parallel) as ex:
                results = list(ex.map(lambda i: run_one(i, task, args, pathlib.Path(tmp)), range(1, args.runs + 1)))

    summary = {"task": task.name, "runs": results,
               "pass_automated": sum(r["pass_automated"] for r in results), "total": len(results)}
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2))
    for r in results:
        print(r)
    print("automated pass: %d/%d" % (summary["pass_automated"], summary["total"]))


if __name__ == "__main__":
    main()

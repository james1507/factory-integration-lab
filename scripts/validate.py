"""Check a task is sound: the grader must FAIL on the broken env and PASS with solution.patch.

Usage: python3 scripts/validate.py tasks/T01-webhook-401
       python3 scripts/validate.py tasks/T01-webhook-401 --controls
       python3 scripts/validate.py tasks/T01-webhook-401 --candidate /path/to/agent/env

--controls also applies each wrong fix in authoring/negative_controls.json; every one must FAIL.
"""
import argparse
import json
import re
import pathlib
import shutil
import subprocess
import sys
import tempfile


def grade(task, env_dir):
    r = subprocess.run(
        [sys.executable, "-m", "unittest", "-v", str(task / "grader" / "test_grader.py")],
        env={"CANDIDATE_DIR": str(env_dir), "PATH": "/usr/bin:/bin"},
        cwd=str(task), capture_output=True, text=True,
    )
    return r.returncode == 0, r.stderr


def failed_checks(log):
    return sorted(m.group(1) for m in re.finditer(r"^FAIL: test_(\w+?)_", log, re.M))


def run_controls(task):
    """Apply each plausible wrong fix to a fresh env copy; return (label, passed, failed check ids)."""
    path = task / "authoring" / "negative_controls.json"
    results = []
    for c in json.loads(path.read_text()) if path.exists() else []:
        with tempfile.TemporaryDirectory() as tmp:
            env = copy_env(task, tmp, "control")
            f = env / c["file"]
            text = f.read_text()
            assert c["old"] in text, "negative control no longer applies: " + c["label"]
            f.write_text(text.replace(c["old"], c["new"]))
            ok, log = grade(task, env)
        results.append((c["label"], ok, failed_checks(log)))
    return results


def copy_env(task, tmp, name):
    dst = pathlib.Path(tmp) / name
    shutil.copytree(task / "env", dst)
    return dst


def main():
    p = argparse.ArgumentParser()
    p.add_argument("task", type=pathlib.Path)
    p.add_argument("--candidate", type=pathlib.Path, help="grade an agent's env/ instead of self-validating")
    p.add_argument("--controls", action="store_true", help="also run authoring/negative_controls.json")
    args = p.parse_args()
    task = args.task.resolve()

    if args.candidate:
        ok, log = grade(task, args.candidate.resolve())
        print(log)
        print("CANDIDATE", "PASS" if ok else "FAIL")
        return 0 if ok else 1

    with tempfile.TemporaryDirectory() as tmp:
        broken = copy_env(task, tmp, "broken")
        broken_ok, broken_log = grade(task, broken)

        fixed = copy_env(task, tmp, "fixed")
        subprocess.run(["patch", "-p1", "-s", "-i", str(task / "solution.patch")], cwd=str(fixed), check=True)
        fixed_ok, fixed_log = grade(task, fixed)

    print("broken env :", "FAIL (expected)" if not broken_ok else "PASS (BAD: task is not broken)")
    print("with fix   :", "PASS (expected)" if fixed_ok else "FAIL (BAD: reference solution fails)")
    if broken_ok or not fixed_ok:
        print(broken_log if broken_ok else fixed_log)
        return 1
    print("\nbroken env grader output:\n" + broken_log)
    if args.controls:
        bad = 0
        for label, ok, failed in run_controls(task):
            print("control %-55s %s" % (label, "PASS (BAD: grader accepts a wrong fix)" if ok
                                         else "FAIL (expected) failed: " + ", ".join(f.upper() for f in failed)))
            bad += ok
        return 1 if bad else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())

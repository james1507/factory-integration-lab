"""Check a task is sound: the grader must FAIL on the broken env and PASS with solution.patch.

Usage: python3 scripts/validate.py tasks/T01-webhook-401
       python3 scripts/validate.py tasks/T01-webhook-401 --candidate /path/to/agent/env
"""
import argparse
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


def copy_env(task, tmp, name):
    dst = pathlib.Path(tmp) / name
    shutil.copytree(task / "env", dst)
    return dst


def main():
    p = argparse.ArgumentParser()
    p.add_argument("task", type=pathlib.Path)
    p.add_argument("--candidate", type=pathlib.Path, help="grade an agent's env/ instead of self-validating")
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
    return 0


if __name__ == "__main__":
    sys.exit(main())

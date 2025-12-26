"""
Minimal repro for demo-lean4 copy.ipynb cells (1-3), runnable from cmd.exe.

Runs:
  from lean_dojo import *
  repo = LeanGitRepo(...)
  trace(repo, dst_dir="traced_lean4-example")
"""

from __future__ import annotations

import os
import sys
import shutil
import time
import traceback
from pathlib import Path


def main() -> int:
    print("=== LeanDojo testing.py ===")
    print("sys.executable:", sys.executable)
    print("cwd:", os.getcwd())

    try:
        from lean_dojo import LeanGitRepo, trace  # type: ignore
        import lean_dojo  # type: ignore

        print("lean_dojo.__file__:", getattr(lean_dojo, "__file__", None))
        print("lean_dojo.__version__:", getattr(lean_dojo, "__version__", None))

        # Disable remote cache to force fresh local tracing
        os.environ["DISABLE_REMOTE_CACHE"] = "1"
        print("DISABLE_REMOTE_CACHE=1 (forcing fresh local trace)")

        # Destination must not exist (LeanDojo asserts dst_dir does not exist).
        # On Windows, deleting a previous run can fail due to transient file locks (e.g. git pack files).
        dst_dir = Path("traced_lean4-example")
        if dst_dir.exists():
            print(f"Existing dst_dir found: {dst_dir.resolve()}")
            print(f"Attempting to remove dst_dir...")
            # Use onerror handler to force delete read-only files (e.g. .git/objects/pack)
            def force_remove_readonly(func, path, excinfo):
                import stat
                os.chmod(path, stat.S_IWRITE)
                func(path)
            shutil.rmtree(dst_dir, onerror=force_remove_readonly)
            print(f"Removed dst_dir successfully")

        repo = LeanGitRepo(
            "https://github.com/yangky11/lean4-example",
            "7b6ecb9ad4829e4e73600a3329baeb3b5df8d23f",
        )
        print("Repo:", repo)

        traced = trace(repo, dst_dir=str(dst_dir))
        print("trace() returned:", traced)
        # Sanity: show where the XML lives (often under `.lake/build/ir`, which can look "missing" if you only check the top-level).
        traced_repo_dir = dst_dir / "lean4-example"
        xml_paths = list(traced_repo_dir.rglob("*.trace.xml"))
        print(f"trace.xml files under {traced_repo_dir}: {len(xml_paths)}")
        for p in xml_paths[:5]:
            print("  xml:", p.relative_to(traced_repo_dir))
        print("OK")
        return 0

    except Exception:
        print("\n--- ERROR ---")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())



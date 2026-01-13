"""
Trace mathlib4 repository with LeanDojo on Windows.

Uses cached version if available, otherwise traces fresh.
"""

from __future__ import annotations

import os
import sys
import shutil
import traceback
from pathlib import Path

# Add local lean_dojo_windows_fixes to path if needed
local_lean_dojo = Path(__file__).parent / "lean_dojo_windows_fixes"
if local_lean_dojo.exists() and str(local_lean_dojo) not in sys.path:
    sys.path.insert(0, str(local_lean_dojo))

# Set up environment before imports
# Set GitHub access token for higher API rate limits
os.environ["GITHUB_ACCESS_TOKEN"] = os.getenv("GITHUB_ACCESS_TOKEN", "YOUR_GITHUB_TOKEN_HERE")

# Enable verbose logging
from loguru import logger
logger.remove()
logger.add(
    sys.stderr,
    level="DEBUG",
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{function}</cyan> - <level>{message}</level>",
    colorize=True
)


def main() -> int:
    print("=== LeanDojo testing_mathlib.py ===")
    print("sys.executable:", sys.executable)
    print("cwd:", os.getcwd())

    try:
        from lean_dojo import LeanGitRepo, trace, TracedRepo
        from lean_dojo.data_extraction.trace import get_traced_repo_path
        from lean_dojo.data_extraction.cache import cache
        import lean_dojo

        print("lean_dojo.__file__:", getattr(lean_dojo, "__file__", None))
        print("lean_dojo.__version__:", getattr(lean_dojo, "__version__", None))

        # Mathlib4 repository
        repo = LeanGitRepo(
            "https://github.com/leanprover-community/mathlib4",
            "29dcec074de168ac2bf835a77ef68bbe069194c5",
        )
        print("Repo:", repo)

        # Check if already cached (either in LeanDojo cache or local traced_mathlib4)
        rel_cache_dir = repo.get_cache_dirname()
        try:
            cached_path = cache.get(rel_cache_dir)
        except (AssertionError, FileNotFoundError):
            # Cache doesn't exist or is corrupted, will trace fresh
            cached_path = None
        
        # Also check local traced_mathlib4 directory
        local_traced = Path("traced_mathlib4") / "mathlib4"
        if local_traced.exists() and (local_traced / ".git").exists():
            print(f"\n✓ Found local traced repo at: {local_traced}")
            cached_path = local_traced
        
        if cached_path is not None:
            print(f"\n✓ Found cached traced repo at: {cached_path}")
            print("Loading from cache (no re-tracing needed)...")
            traced = TracedRepo.load_from_disk(cached_path, build_deps=True)
            print("trace() returned:", traced)
        else:
            print("\n*** No cache found. Tracing mathlib4 (this takes HOURS and 50+ GB) ***\n")
            
            # Destination must not exist (LeanDojo asserts dst_dir does not exist).
            dst_dir = Path("traced_mathlib4")
            if dst_dir.exists():
                print(f"Existing dst_dir found: {dst_dir.resolve()}")
                print(f"Attempting to remove dst_dir...")
                def force_remove_readonly(func, path, excinfo):
                    import stat
                    os.chmod(path, stat.S_IWRITE)
                    func(path)
                shutil.rmtree(dst_dir, onerror=force_remove_readonly)
                print(f"Removed dst_dir successfully")

            traced = trace(repo, dst_dir=str(dst_dir))
            print("trace() returned:", traced)
            cached_path = dst_dir / "mathlib4"
        
        # Show summary of traced files
        traced_repo_dir = cached_path if cached_path else dst_dir / "mathlib4"
        xml_paths = list(Path(traced_repo_dir).rglob("*.trace.xml"))
        print(f"\ntrace.xml files under {traced_repo_dir}: {len(xml_paths)}")
        for p in xml_paths[:10]:
            print("  xml:", p.relative_to(traced_repo_dir))
        if len(xml_paths) > 10:
            print(f"  ... and {len(xml_paths) - 10} more")
        print("\nOK - Mathlib4 loaded/traced successfully!")
        return 0

    except Exception:
        print("\n--- ERROR ---")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


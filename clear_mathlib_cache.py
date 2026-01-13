"""Clear all cache and temp files for mathlib4 tracing."""
from pathlib import Path
import os
import shutil
import stat
import sys

# Add local lean_dojo_windows_fixes to path if needed
local_lean_dojo = Path(__file__).parent / "lean_dojo_windows_fixes"
if local_lean_dojo.exists() and str(local_lean_dojo) not in sys.path:
    sys.path.insert(0, str(local_lean_dojo))

try:
    from lean_dojo import LeanGitRepo
except ImportError:
    print("Warning: lean_dojo not found. Will clear cache paths manually.")
    LeanGitRepo = None

print("=== Clearing Mathlib4 Cache ===")

# Mathlib4 repository info (used for cache path calculation)
mathlib_url = "https://github.com/leanprover-community/mathlib4"
mathlib_commit = "29dcec074de168ac2bf835a77ef68bbe069194c5"

if LeanGitRepo:
    repo = LeanGitRepo(mathlib_url, mathlib_commit)
else:
    repo = None

# Function to force remove readonly files
def force_remove_readonly(func, path, excinfo):
    os.chmod(path, stat.S_IWRITE)
    func(path)

paths_cleared = []

# 1. Clear LeanDojo cache directory
cache_dir = Path(os.environ.get("CACHE_DIR", Path.home() / ".cache/lean_dojo"))
if repo:
    rel_dir = repo.get_cache_dirname() / repo.name
    cache_path = cache_dir / rel_dir
    if cache_path.exists():
        print(f"Clearing cache: {cache_path}")
        shutil.rmtree(cache_path, ignore_errors=True, onerror=force_remove_readonly)
        paths_cleared.append(str(cache_path))

# 2. Clear any mathlib-related cache directories and downloaded files
if cache_dir.exists():
    for p in cache_dir.glob("*mathlib*"):
        if p.is_dir():
            print(f"Clearing mathlib cache: {p}")
            shutil.rmtree(p, ignore_errors=True, onerror=force_remove_readonly)
            paths_cleared.append(str(p))
        elif p.is_file():
            # Also remove any downloaded .tar.gz files
            print(f"Clearing mathlib cache file: {p}")
            try:
                p.unlink()
                paths_cleared.append(str(p))
            except:
                pass

# 3. Clear local traced_mathlib4 directory
base_dir = Path(__file__).parent
local_traced_dir = base_dir / "traced_mathlib4"
if local_traced_dir.exists():
    print(f"Clearing local traced dir: {local_traced_dir}")
    shutil.rmtree(local_traced_dir, ignore_errors=True, onerror=force_remove_readonly)
    paths_cleared.append(str(local_traced_dir))

# 4. Clear temp directory files with mathlib in name
temp_dir = Path(os.environ.get("TEMP", os.environ.get("TMP", Path.home() / "AppData" / "Local" / "Temp")))
if temp_dir.exists():
    for p in temp_dir.glob("tmp*"):
        if "mathlib" in str(p).lower() and p.is_dir():
            print(f"Clearing temp dir: {p}")
            shutil.rmtree(p, ignore_errors=True, onerror=force_remove_readonly)
            paths_cleared.append(str(p))

# 5. Clear TMP_DIR if set and contains mathlib
if "TMP_DIR" in os.environ:
    tmp_dir = Path(os.environ["TMP_DIR"])
    if tmp_dir.exists():
        for p in tmp_dir.glob("*mathlib*"):
            if p.is_dir():
                print(f"Clearing TMP_DIR mathlib: {p}")
                shutil.rmtree(p, ignore_errors=True, onerror=force_remove_readonly)
                paths_cleared.append(str(p))
            elif p.is_file():
                print(f"Clearing TMP_DIR mathlib file: {p}")
                try:
                    p.unlink()
                    paths_cleared.append(str(p))
                except:
                    pass

# 6. Clear any .tar.gz files in cache directory (downloaded cache files)
if cache_dir.exists():
    for p in cache_dir.glob("*.tar.gz"):
        if "mathlib" in str(p).lower():
            print(f"Clearing downloaded cache file: {p}")
            try:
                p.unlink()
                paths_cleared.append(str(p))
            except:
                pass

if paths_cleared:
    print(f"\n[OK] Cleared {len(paths_cleared)} cache/temp locations")
    for p in paths_cleared:
        print(f"  - {p}")
else:
    print("\n[OK] No mathlib4 cache/temp files found to clear")

print("\nCache clearing complete!")

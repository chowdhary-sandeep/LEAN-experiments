"""Clear the cached traced repo for lean4-example."""
from pathlib import Path
import os
import shutil
import sys

# Add local lean_dojo_windows_fixes to path if needed
local_lean_dojo = Path(__file__).parent / "lean_dojo_windows_fixes"
if local_lean_dojo.exists() and str(local_lean_dojo) not in sys.path:
    sys.path.insert(0, str(local_lean_dojo))

try:
    from lean_dojo import LeanGitRepo
except ImportError:
    print("Warning: lean_dojo not found. Cannot compute exact cache paths.")
    LeanGitRepo = None

if LeanGitRepo:
    repo = LeanGitRepo(
        "https://github.com/yangky11/lean4-example",
        "7b6ecb9ad4829e4e73600a3329baeb3b5df8d23f",
    )
else:
    repo = None

# Check both the default cache location and the local traced directory
cache_dir = Path(os.environ.get("CACHE_DIR", Path.home() / ".cache/lean_dojo"))
if repo:
    rel_dir = repo.get_cache_dirname() / repo.name
    cache_path = cache_dir / rel_dir
else:
    # Fallback: try to find lean4-example cache manually
    cache_path = None
    if cache_dir.exists():
        for p in cache_dir.glob("*lean4-example*"):
            if p.is_dir():
                cache_path = p
                break

# Also check the local traced directory (contains repo as subdirectory)
base_dir = Path(__file__).parent
local_traced_dir = base_dir / "traced_lean4-example"
if repo:
    local_repo_path = local_traced_dir / repo.name  # e.g., traced_lean4-example/lean4-example
else:
    local_repo_path = local_traced_dir / "lean4-example"  # fallback

paths_to_clear = []
if cache_path and cache_path.exists():
    paths_to_clear.append(("cache", cache_path))
if local_traced_dir.exists():
    paths_to_clear.append(("local traced dir", local_traced_dir))
if local_repo_path.exists():
    paths_to_clear.append(("local repo", local_repo_path))

print(f"Default cache path: {cache_path}")
print(f"Local traced path: {local_traced_dir}")

if paths_to_clear:
    for name, path in paths_to_clear:
        print(f"Clearing {name} at: {path}")
        shutil.rmtree(path, ignore_errors=True)
    print("Cache cleared")
else:
    print("Cache not found at either location")


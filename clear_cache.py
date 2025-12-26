"""Clear the cached traced repo for lean4-example."""
from pathlib import Path
import os
import shutil
from lean_dojo import LeanGitRepo

repo = LeanGitRepo(
    "https://github.com/yangky11/lean4-example",
    "7b6ecb9ad4829e4e73600a3329baeb3b5df8d23f",
)

# Check both the default cache location and the local traced directory
cache_dir = Path(os.environ.get("CACHE_DIR", Path.home() / ".cache/lean_dojo"))
rel_dir = repo.get_cache_dirname() / repo.name
cache_path = cache_dir / rel_dir

# Also check the local traced directory (contains repo as subdirectory)
base_dir = Path(__file__).parent.parent
local_traced_dir = base_dir / "traced_lean4-example"
local_repo_path = local_traced_dir / repo.name  # e.g., traced_lean4-example/lean4-example

paths_to_clear = []
if cache_path.exists():
    paths_to_clear.append(("cache", cache_path))
if local_traced_dir.exists():
    paths_to_clear.append(("local traced dir", local_traced_dir))
if local_repo_path.exists():
    paths_to_clear.append(("local repo", local_repo_path))

print(f"Default cache path: {cache_path}")
print(f"Local traced path: {local_traced_path}")

if paths_to_clear:
    for name, path in paths_to_clear:
        print(f"Clearing {name} at: {path}")
        shutil.rmtree(path, ignore_errors=True)
    print("Cache cleared")
else:
    print("Cache not found at either location")


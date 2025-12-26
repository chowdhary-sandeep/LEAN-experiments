"""
Trace mathlib4 repository with LeanDojo on Windows.
Clears cache and runs fresh trace.
"""

import os
import sys
import shutil
from pathlib import Path

# Set GitHub access token
# Set GitHub access token (optional, for higher API rate limits)
# Get your token from: https://github.com/settings/tokens
# os.environ["GITHUB_ACCESS_TOKEN"] = "your_token_here"

# Enable verbose logging with loguru
from loguru import logger

# Remove default handler and add one with DEBUG level
logger.remove()  # Remove default handler
logger.add(
    sys.stderr,
    level="DEBUG",  # Show all debug messages
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    colorize=True
)

print("=== Mathlib4 Tracing Script ===")
print(f"Python: {sys.executable}")
print(f"CWD: {os.getcwd()}")

# Clear cache before tracing
print("\n=== Clearing cache ===")

# Clear temp cache
temp_dir = Path(os.environ.get("TEMP", r"C:\Users\chowdhary\AppData\Local\Temp"))
for p in temp_dir.glob("tmp*"):
    if "mathlib" in str(p).lower():
        print(f"Removing temp: {p}")
        shutil.rmtree(p, ignore_errors=True)

# Clear LeanDojo cache
cache_dir = Path.home() / ".cache" / "lean_dojo"
for p in cache_dir.glob("*mathlib*"):
    print(f"Removing cache: {p}")
    shutil.rmtree(p, ignore_errors=True)

# Clear local traced_mathlib4 if exists
local_traced = Path("traced_mathlib4")
if local_traced.exists():
    print(f"Removing local: {local_traced}")
    def force_remove_readonly(func, path, excinfo):
        import stat
        os.chmod(path, stat.S_IWRITE)
        func(path)
    shutil.rmtree(local_traced, onerror=force_remove_readonly)

print("Cache cleared!")

# Import and trace
print("\n=== Starting trace ===")
from lean_dojo import LeanGitRepo, trace

repo = LeanGitRepo(
    "https://github.com/leanprover-community/mathlib4",
    "29dcec074de168ac2bf835a77ef68bbe069194c5",
)

print(f"Repo: {repo}")
print("\n*** WARNING: Tracing mathlib4 takes several HOURS ***\n")

# The trace function uses tqdm for progress bars - you'll see:
# - "X/Y [time remaining]" progress bars for file processing
# - DEBUG messages showing what's happening
# - INFO messages for major milestones

traced_repo = trace(repo, dst_dir="traced_mathlib4")

print(f"\n=== Trace complete ===")
print(f"Result: {traced_repo}")

# Show summary
traced_dir = Path("traced_mathlib4") / "mathlib4"
if traced_dir.exists():
    xml_count = len(list(traced_dir.rglob("*.trace.xml")))
    print(f"Generated {xml_count} .trace.xml files")



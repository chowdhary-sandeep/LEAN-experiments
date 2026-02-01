"""Remove any GitHub token from notebook source and clear outputs before upload.
Run before git add if you ever set GITHUB_ACCESS_TOKEN in a cell.
"""
import json
import re
from pathlib import Path

SAFE_LINE = 'os.environ.setdefault("GITHUB_ACCESS_TOKEN", "")\n'
TOKEN_PATTERN = re.compile(
    r'os\.environ\s*\[\s*["\']GITHUB_ACCESS_TOKEN["\']\s*\]\s*=\s*["\'][^"\']+["\']'
)


def process_notebook(path: Path) -> bool:
    """Replace token assignment with setdefault and clear outputs. Return True if changed."""
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    changed = False
    for cell in data.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        # Strip token from source
        src = cell.get("source", [])
        if isinstance(src, str):
            src = [src]
        new_src = []
        for line in src:
            if TOKEN_PATTERN.search(line):
                new_src.append(SAFE_LINE)
                changed = True
            else:
                new_src.append(line)
        cell["source"] = new_src
        # Clear outputs so no printed env leaks token
        if cell.get("outputs"):
            cell["outputs"] = []
            changed = True
    if changed:
        path.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    return changed


def main():
    root = Path(__file__).parent
    for path in root.glob("**/*.ipynb"):
        if "venv" in str(path) or ".ipynb_checkpoints" in str(path):
            continue
        if process_notebook(path):
            print(f"Cleaned: {path.relative_to(root)}")
    print("Done. No token in notebook source or outputs.")


if __name__ == "__main__":
    main()

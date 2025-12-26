# LeanDojo Windows Compatibility Fixes

This repository contains Windows-compatible fixes for [LeanDojo](https://github.com/lean-dojo/LeanDojo), an open-source framework for integrating LLMs with the Lean proof assistant.

## Overview

This fork includes comprehensive Windows compatibility fixes that enable LeanDojo to work seamlessly on Windows systems, including:

- **Path handling**: Cross-platform path separator normalization (Windows backslashes vs Unix forward slashes)
- **Unicode encoding**: UTF-8 encoding for all file operations to handle Unicode characters (Greek letters, mathematical symbols, etc.)
- **Process spawning**: Windows-compatible process management using `pexpect.popen_spawn.PopenSpawn`
- **File locking**: Proper temporary file handling on Windows to avoid file locking issues
- **Line endings**: CRLF/LF normalization for cross-platform compatibility

## Key Fixes

### 1. Path Handling (`ExtractData.lean`, `utils.py`)
- Normalizes Windows backslashes to forward slashes before path operations
- Handles multiple `.olean` file layouts (`build/lib/lean/` and `build/lib/`)
- Defensive path cleanup to remove build directory fragments

### 2. Unicode Encoding (Multiple Files)
- All file I/O operations explicitly use `encoding="utf-8"`
- Fixed in: `dojo.py`, `trace.py`, `lean.py`, `traced_data.py`
- Prevents `UnicodeEncodeError` and `UnicodeDecodeError` on Windows

### 3. Interactive Dojo (`dojo.py`)
- Windows-compatible process spawning with `PopenSpawn`
- Line ending handling for Windows CRLF (`\r\n`)
- Temporary file management that works on Windows

### 4. Tactic Extraction
- Restored full tactic extraction functionality
- Proper `ContextInfo` handling and state merging
- Complete tactic state before/after extraction

## Installation

1. Clone this repository:
```bash
git clone <your-repo-url>
cd lean-dojo
```

2. Create a virtual environment:
```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
```

3. Install LeanDojo:
```bash
pip install -e .
```

4. Set up GitHub access token (optional, for higher API rate limits):
```bash
set GITHUB_ACCESS_TOKEN=your_token_here
```

## Usage

See `demo-lean4.ipynb` for examples of:
- Tracing Lean repositories
- Loading traced repositories
- Interactive theorem proving with Dojo
- Extracting tactics and premises

## Documentation

See `plan.md` for detailed documentation of all fixes and changes.

## Notes

- `traced_*` folders are excluded from git (see `.gitignore`)
- All fixes maintain backward compatibility with Unix/Linux systems
- The fixes are proper solutions, not workarounds

## License

Same as original LeanDojo project.


# LeanDojo Windows Compatibility Fixes - Copy-Paste Package

This folder contains the complete `lean_dojo` package with all Windows compatibility fixes applied. **Just copy-paste the entire folder** to your Python environment and it will work immediately.

## Installation (3 Steps)

### Step 1: Install Dependencies
```bash
pip install lean-dojo
```
This installs all required packages (pexpect, ray, loguru, etc.).

### Step 2: Find Your Python Site-Packages
```bash
python -c "import site; print(site.getsitepackages()[0])"
```
This prints something like: `C:\Users\YourName\AppData\Local\Programs\Python\Python312\Lib\site-packages`

### Step 3: Copy the Entire Folder
**Simply copy the `lean_dojo` folder** (this entire directory structure) to your site-packages:

**Windows:**
```cmd
xcopy /E /I /Y "lean_dojo" "C:\path\to\site-packages\lean_dojo"
```

**Or manually:**
- Copy the entire `lean_dojo` folder to: `{site-packages}\lean_dojo`
- Replace the existing folder (backup first if you want)

### Step 4: Verify
```python
from lean_dojo import LeanGitRepo, trace, Dojo
print("✅ Windows compatibility working!")
```

## That's It!

The entire package is self-contained and portable. All paths use relative references (`__file__`), so it works regardless of where it's installed.

## What's Fixed?

- ✅ **Path Handling** - Windows backslashes normalized, cross-platform support
- ✅ **Unicode Encoding** - All file I/O uses UTF-8 (handles Greek letters, math symbols)
- ✅ **Process Spawning** - Windows-compatible with `PopenSpawn`
- ✅ **Line Endings** - Handles Windows CRLF (`\r\n`)
- ✅ **File Locking** - Proper temporary file management on Windows
- ✅ **Tactic Extraction** - Full functionality restored

## Files Included

All modified files are included:
- `data_extraction/ExtractData.lean` - Lean script (Windows path fixes)
- `data_extraction/trace.py` - Repository tracing
- `data_extraction/lean.py` - Lean file handling (Unicode fixes)
- `data_extraction/traced_data.py` - Traced data loading/saving
- `interaction/dojo.py` - Interactive theorem proving (Windows process fixes)
- `utils.py` - Utility functions (path fixes)

Plus all original files needed for the package to work.

## Compatibility

- ✅ **Windows 10/11** - Fully tested
- ✅ **Unix/Linux** - 100% backward compatible
- ✅ **macOS** - Should work (uses cross-platform code)

## Notes

- The `__pycache__` folders can be included or excluded - Python will handle bytecode automatically
- All fixes are proper engineering solutions, not workarounds
- Tested on both small repos (`lean4-example`) and large repos (`mathlib4`)

## Troubleshooting

**Issue:** `ModuleNotFoundError: No module named 'lean_dojo'`
- Make sure you copied to the correct `site-packages` directory
- Check: `python -c "import lean_dojo; print(lean_dojo.__file__)"`

**Issue:** Still getting errors
- Make sure you copied the **entire folder**, not just individual files
- Verify all subdirectories (`data_extraction/`, `interaction/`) were copied

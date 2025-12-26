# Copy-Paste Installation - LeanDojo Windows Fixes

## ✅ YES - It Will Work!

You can copy the entire `lean_dojo` folder from `.venv/Lib/site-packages/lean_dojo` to your environment's `site-packages` folder and it will work immediately.

## Quick Installation (3 Steps)

### Step 1: Install Dependencies
```bash
pip install lean-dojo
```
This installs all required packages (pexpect, ray, loguru, etc.) but with the original (non-Windows-compatible) code.

### Step 2: Find Your Python Site-Packages
```bash
python -c "import site; print(site.getsitepackages()[0])"
```
This prints something like: `C:\Users\YourName\AppData\Local\Programs\Python\Python312\Lib\site-packages`

### Step 3: Copy the Fixed Package
**Option A: Copy entire folder (easiest)**
```cmd
# Backup original (optional)
xcopy /E /I "%PYTHON_SITE_PACKAGES%\lean_dojo" "%PYTHON_SITE_PACKAGES%\lean_dojo.backup"

# Copy the fixed version
xcopy /E /I /Y "path\to\lean_dojo_windows_fixes\lean_dojo" "%PYTHON_SITE_PACKAGES%\lean_dojo"
```

**Option B: Copy just the modified files**
```cmd
copy /Y "lean_dojo\data_extraction\ExtractData.lean" "%PYTHON_SITE_PACKAGES%\lean_dojo\data_extraction\"
copy /Y "lean_dojo\data_extraction\trace.py" "%PYTHON_SITE_PACKAGES%\lean_dojo\data_extraction\"
copy /Y "lean_dojo\data_extraction\lean.py" "%PYTHON_SITE_PACKAGES%\lean_dojo\data_extraction\"
copy /Y "lean_dojo\data_extraction\traced_data.py" "%PYTHON_SITE_PACKAGES%\lean_dojo\data_extraction\"
copy /Y "lean_dojo\interaction\dojo.py" "%PYTHON_SITE_PACKAGES%\lean_dojo\interaction\"
copy /Y "lean_dojo\utils.py" "%PYTHON_SITE_PACKAGES%\lean_dojo\"
```

### Step 4: Verify
```python
from lean_dojo import LeanGitRepo, trace, Dojo
print("✅ Windows compatibility working!")
```

## Why It Works

1. **All paths are relative** - Uses `__file__` to find resources, so it works anywhere
2. **No hardcoded paths** - Everything is portable
3. **Python handles bytecode** - `__pycache__` will be regenerated if needed
4. **Dependencies already installed** - Step 1 handles that

## What Gets Copied

```
lean_dojo/
├── __init__.py              # Package initialization
├── constants.py             # Configuration
├── utils.py                 # ✅ MODIFIED - Windows fixes
├── data_extraction/
│   ├── ExtractData.lean     # ✅ MODIFIED - Windows fixes
│   ├── trace.py             # ✅ MODIFIED - Windows fixes
│   ├── lean.py              # ✅ MODIFIED - Windows fixes
│   ├── traced_data.py       # ✅ MODIFIED - Windows fixes
│   ├── ast.py               # Original
│   └── cache.py             # Original
└── interaction/
    ├── dojo.py              # ✅ MODIFIED - Windows fixes
    ├── Lean4Repl.lean       # Original
    └── parse_goals.py       # Original
```

## Notes

- **`__pycache__` folders**: Can be included or excluded - Python will handle it
- **Python version**: Should work with Python 3.8+ (same as LeanDojo requirements)
- **Backward compatible**: All fixes work on Unix/Linux too, so it's safe to copy

## Troubleshooting

**Issue:** `ModuleNotFoundError: No module named 'lean_dojo'`
- Make sure you copied to the correct `site-packages` directory
- Check: `python -c "import lean_dojo; print(lean_dojo.__file__)"`

**Issue:** Still getting Unicode errors
- Make sure ALL modified files were copied (especially `dojo.py` and `lean.py`)

**Issue:** Path errors
- Verify `ExtractData.lean` and `utils.py` were copied correctly


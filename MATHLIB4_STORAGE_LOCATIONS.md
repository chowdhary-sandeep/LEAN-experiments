# Mathlib4 Storage Locations Documentation

This document catalogs all locations where mathlib4-related files are stored by LeanDojo, excluding the main traced repository at `traced_mathlib4\mathlib4`.

## Summary of Storage Locations

Based on codebase analysis of `testing_mathlib.py` and the LeanDojo codebase, here are all locations where mathlib4 files may be stored:

---

## 1. **Main Cache Directory** (Primary Storage)

**Location:** `C:\Users\chowdhary\.cache\lean_dojo\leanprover-community-mathlib4-29dcec074de168ac2bf835a77ef68bbe069194c5\mathlib4`

**Source:** `lean_dojo/constants.py` (lines 25-29) and `lean_dojo/data_extraction/cache.py` (lines 90-103)

**Structure:**
```
.cache/lean_dojo/
└── leanprover-community-mathlib4-{commit}/
    └── mathlib4/
        ├── .git/                          # Git repository
        ├── .lake/                         # Lake build directory
        │   ├── build/
        │   │   └── ir/                    # Extracted data
        │   │       ├── *.ast.json         # AST files
        │   │       ├── *.dep_paths        # Dependency paths
        │   │       └── *.trace.xml        # Traced XML files
        │   └── packages/                 # Dependencies
        ├── Mathlib/                       # Source files
        └── [other repo files]
```

**How it's created:**
- `trace.py:get_traced_repo_path()` calls `cache.store()` after tracing
- `cache.py:store()` uses `shutil.copytree()` to copy from temp directory

**Cache directory name format:** `{user_name}-{repo_name}-{commit_hash}`
- For mathlib4: `leanprover-community-mathlib4-29dcec074de168ac2bf835a77ef68bbe069194c5`

---

## 2. **Temporary Directory** (During Tracing)

**Location:** System temp directory (varies by OS/env)

**Windows Default:** `%TEMP%` or `%TMP%` (typically `C:\Users\chowdhary\AppData\Local\Temp`)

**Source:** `lean_dojo/utils.py` (lines 22-59) and `lean_dojo/constants.py` (line 40)

**Structure:**
```
{TEMP}/tmp{random}/
└── mathlib4/                              # Cloned during tracing
    ├── .git/
    ├── .lake/
    │   ├── build/
    │   │   └── ir/                        # Generated during ExtractData.lean
    │   │       ├── *.ast.json
    │   │       ├── *.dep_paths
    │   │       └── *.trace.xml
    │   └── packages/
    └── [repo files]
```

**How it's created:**
- `trace.py:get_traced_repo_path()` uses `working_directory()` context manager
- `utils.py:working_directory()` creates `tempfile.TemporaryDirectory()` if `TMP_DIR` env var is set, uses that; otherwise uses system temp
- `trace.py:_trace()` clones repo into temp directory and processes it
- **Note:** Temp directories are supposed to be cleaned up automatically, but on Windows with `ignore_cleanup_errors=True`, they may persist

**Environment Variable:** `TMP_DIR` (if set, overrides default temp location)

---

## 3. **Downloaded Cache Files** (.tar.gz)

**Location:** `C:\Users\chowdhary\.cache\lean_dojo\leanprover-community-mathlib4-29dcec074de168ac2bf835a77ef68bbe069194c5.tar.gz`

**Source:** `lean_dojo/data_extraction/cache.py` (lines 70-85)

**Structure:**
- Single compressed archive file
- Downloaded from remote cache if available
- Extracted to cache directory and then deleted

**How it's created:**
- `cache.py:get()` downloads from `REMOTE_CACHE_URL` if not `DISABLE_REMOTE_CACHE`
- Remote URL: `https://dl.fbaipublicfiles.com/lean-dojo/{dirname}.tar.gz`
- File is extracted and then removed (line 82)

**Note:** This file should be deleted after extraction, but may persist if extraction fails or is interrupted.

---

## 4. **Local Traced Directory** (User-Specified)

**Location:** `C:\Users\chowdhary\Desktop\lean-dojo\traced_mathlib4\mathlib4`

**Source:** `testing_mathlib.py` (lines 65-68, 79-92) and `lean_dojo/data_extraction/cache.py` (lines 54-63)

**Structure:**
```
traced_mathlib4/
└── mathlib4/
    ├── .git/
    ├── .lake/
    │   └── build/
    │       └── ir/
    │           └── *.trace.xml
    └── [repo files]
```

**How it's created:**
- `testing_mathlib.py` calls `trace(repo, dst_dir="traced_mathlib4")`
- `trace.py:trace()` copies from cache to `dst_dir` using `shutil.copytree()` (line 281)
- This is a **copy** of the cached version, not a new trace

**Note:** This is the location you specified to exclude from the search.

---

## 5. **Cache Lock File**

**Location:** `C:\Users\chowdhary\.cache\lean_dojo\.lock` (or `lean_dojo.lock`)

**Source:** `lean_dojo/data_extraction/cache.py` (lines 38-42)

**Structure:**
- Single lock file for cache directory
- Used by `FileLock` to prevent concurrent cache access

---

## 6. **ExtractData.lean Temporary Files**

**Location:** Inside temp directory during tracing

**Source:** `lean_dojo/data_extraction/trace.py` (lines 180, 191)

**Files:**
- `ExtractData.lean` - Copied to repo root during tracing, then deleted
- Generated files in `.lake/build/ir/`:
  - `*.ast.json` - AST representations
  - `*.dep_paths` - Import dependency paths

**How it's created:**
- `trace.py:_trace()` copies `ExtractData.lean` to repo directory (line 180)
- Lean processes it and generates `.ast.json` and `.dep_paths` files
- `ExtractData.lean` is removed after processing (line 191)
- Generated files remain in `.lake/build/ir/` structure

---

## 7. **Lean4Repl.lean Files**

**Location:** Inside traced repo directories

**Source:** `lean_dojo/data_extraction/trace.py` (lines 193-213)

**Files:**
- `Lean4Repl.lean` - Copied to repo root
- Modified `lakefile.lean` or `lakefile.toml` - Appended with Lean4Repl library

**How it's created:**
- `trace.py:_trace()` copies `Lean4Repl.lean` to repo (line 198)
- Appends to `lakefile.lean` or `lakefile.toml` (lines 201-206)
- Built with `lake build Lean4Repl` (line 209)

---

## 8. **XML Trace Files** (.trace.xml)

**Location:** Inside traced repos at `.lake/build/ir/**/*.trace.xml`

**Source:** `lean_dojo/data_extraction/traced_data.py` (lines 947-951, 1179-1198)

**Structure:**
```
.lake/build/ir/
├── Mathlib.trace.xml
├── Mathlib/
│   ├── Tactic.trace.xml
│   ├── Algebra/
│   │   └── *.trace.xml
│   └── [other modules]/
└── [other files]/
```

**How it's created:**
- `traced_data.py:save_to_disk()` saves all traced files as XML
- Uses `_save_xml_to_disk()` which writes UTF-8 encoded XML files
- Path determined by `to_xml_path()` utility function

---

## 9. **Git Clone Locations** (During Initial Clone)

**Location:** Inside temp directory during `clone_and_checkout()`

**Source:** `lean_dojo/data_extraction/lean.py` (lines 643-648)

**How it's created:**
- `lean.py:clone_and_checkout()` uses `Repo.clone_from()` to clone repo
- Clones to current working directory (which is temp dir during tracing)
- Checks out specific commit and updates submodules

---

## 10. **Lake Build Artifacts**

**Location:** Inside repo directories at `.lake/build/` and `.lake/packages/`

**Source:** `lean_dojo/data_extraction/trace.py` (lines 167, 172-177)

**Structure:**
```
.lake/
├── build/
│   ├── lib/                               # Compiled .olean files
│   └── ir/                                # Extracted data
│       ├── *.ast.json
│       ├── *.dep_paths
│       └── *.trace.xml
└── packages/                              # Dependencies
    ├── lean4/                             # Lean 4 stdlib (copied)
    ├── batteries/
    ├── aesop/
    └── [other deps]/
```

**How it's created:**
- `trace.py:_trace()` runs `lake build` (line 167)
- Copies Lean 4 stdlib to `.lake/packages/lean4` (line 177)
- Lake downloads and builds dependencies in `.lake/packages/`

---

## Environment Variables Affecting Storage

1. **CACHE_DIR**: Overrides default cache location
   - Default: `~/.cache/lean_dojo`
   - Set via: `os.environ["CACHE_DIR"]`

2. **TMP_DIR**: Overrides temporary directory
   - Default: System temp directory
   - Set via: `os.environ["TMP_DIR"]`

3. **DISABLE_REMOTE_CACHE**: Prevents downloading from remote cache
   - Set via: `os.environ["DISABLE_REMOTE_CACHE"]`

4. **LOCAL_TRACED_DIR**: Alternative local traced directory
   - Checked by `cache.py:get()` (lines 56-63)
   - Set via: `os.environ["LOCAL_TRACED_DIR"]`

---

## File Types Generated

1. **.ast.json**: Abstract Syntax Tree representations
2. **.dep_paths**: Import dependency paths (one per .lean file)
3. **.trace.xml**: Complete traced file with tactics, premises, etc.
4. **.olean**: Compiled Lean files (build artifacts)
5. **.tar.gz**: Compressed cache archives (temporary)

---

## Cleanup Behavior

- **Temp directories**: Should auto-cleanup, but Windows may leave them due to `ignore_cleanup_errors=True`
- **Cache directory**: Persists permanently until manually deleted
- **Downloaded .tar.gz**: Should be deleted after extraction
- **ExtractData.lean**: Deleted after processing
- **Local traced dir**: Persists until manually deleted

---

## Code Flow Summary

1. `testing_mathlib.py` calls `trace(repo, dst_dir="traced_mathlib4")`
2. `trace.py:trace()` calls `get_traced_repo_path()`
3. `get_traced_repo_path()` checks cache, if not found:
   - Creates temp directory via `working_directory()`
   - Calls `_trace()` which:
     - Clones repo to temp dir
     - Builds with `lake build`
     - Runs `ExtractData.lean` to generate `.ast.json` and `.dep_paths`
     - Builds `Lean4Repl.lean`
   - Creates `TracedRepo` from files
   - Calls `save_to_disk()` to generate `.trace.xml` files
   - Calls `cache.store()` to copy to cache directory
4. Finally, `trace()` copies from cache to `dst_dir` if specified

---

## Notes

- All paths use `Path` objects for cross-platform compatibility
- Windows paths are normalized (backslashes handled)
- UTF-8 encoding is used for all text files
- Git repositories are cloned with `no_checkout=True` then specific commit checked out
- Submodules are updated recursively during clone

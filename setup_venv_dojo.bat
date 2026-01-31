@echo off
REM Create venv_dojo and install lean-dojo.
REM Requires: Python 3.9-3.12 (lean-dojo does not support 3.13 yet), Git, wget, elan.

set PYEXE=
for %%v in (3.12 3.11 3.10 3.9) do (
  where py -%%v -c "import sys; sys.exit(0)" >nul 2>&1 && set PYEXE=py -%%v && goto :found
)
where python >nul 2>&1 && for /f "tokens=2" %%a in ('python -c "import sys; print(sys.version_info.minor)" 2^>nul') do (
  if %%a LSS 13 (set PYEXE=python && goto :found)
)
echo ERROR: Need Python 3.9, 3.10, 3.11, or 3.12. lean-dojo requires Python ^< 3.13.
echo Install Python 3.12 from https://www.python.org/downloads/ and ensure "py" launcher or "python" is 3.12.
exit /b 1

:found
echo Using: %PYEXE%
"%PYEXE%" -m venv venv_dojo
call venv_dojo\Scripts\activate.bat
pip install --upgrade pip
pip install lean-dojo
echo.
echo Done. Activate with: venv_dojo\Scripts\activate.bat
exit /b 0

@echo off
REM Ensure python 3 is available
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Python is required but not found. Please install Python 3.
    exit /b 1
)

python -c "import sys; sys.exit(0 if sys.version_info >= (3,0) else 1)"
if %ERRORLEVEL% NEQ 0 (
    echo Python 3 is required. Please install Python 3.
    exit /b 1
)

python bootstrap.py

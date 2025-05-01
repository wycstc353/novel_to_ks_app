@echo off
REM Installs Python dependencies for Novel Converter App

echo Checking for Python...
python --version > nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found in PATH. Please install Python and add it to PATH.
    goto :eof
)

echo Checking for pip...
python -m pip --version > nul 2>&1
if errorlevel 1 (
    echo ERROR: pip not found. Ensure your Python installation includes pip.
    goto :eof
)

echo.
echo Installing dependencies from requirements.txt...
echo If you encounter permission issues, try running this script as Administrator.
echo.

python -m pip install -r requirements.txt

echo.
echo ==============================================
echo Dependency installation finished. Check for errors above.
echo If successful, you can now run run_app.bat
echo ==============================================
echo.

pause
:eof
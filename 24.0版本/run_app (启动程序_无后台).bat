@echo off

echo Launching application using Python Launcher (pyw.exe)...
start "" /B pyw -3 main_app.py


if %errorlevel% neq 0 (
    echo Failed to launch using 'pyw'. Trying 'pythonw' directly...

    start "" /B pythonw main_app.py
    if %errorlevel% neq 0 (
      echo ERROR: Could not find 'pyw.exe' or 'pythonw.exe'. 
      echo Please ensure Python is installed correctly and added to PATH,
      echo or the Python Launcher is available.
      pause
    )
)

exit /B 0
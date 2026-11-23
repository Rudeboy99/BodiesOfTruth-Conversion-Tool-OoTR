@echo off
rem SPDX-License-Identifier: GPL-3.0-or-later
rem Copyright (C) 2026 BodiesOfTruth contributors. See LICENSE.txt and CREDITS.txt.
rem BodiesOfTruth V1.3.1 GUI. Double-click, or drag a mod folder onto this file.
rem First run: finds (or installs) Python, sets up the tool's packages, then opens the window.
setlocal
cd /d "%~dp0"
call "%~dp0app\lib\find_python.bat" || goto :failed
"%PYEXE%" "%~dp0app\lib\bootstrap.py" gui %*
if errorlevel 1 goto :failed
exit /b 0
:failed
echo.
pause
exit /b 1

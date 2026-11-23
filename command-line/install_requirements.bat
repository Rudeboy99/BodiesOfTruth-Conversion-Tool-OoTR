@echo off
rem SPDX-License-Identifier: GPL-3.0-or-later
rem Copyright (C) 2026 BodiesOfTruth contributors. See LICENSE.txt and CREDITS.txt.
rem Optional: the launchers do this setup by themselves on first run. Run this to repair it.
rem Installs the package versions the converter was built and tested with, into the tool's own
rem environment (%LOCALAPPDATA%\BodiesOfTruth; delete that folder to remove it).
setlocal
cd /d "%~dp0.."
call "%~dp0..\app\lib\find_python.bat" || goto :end
"%PYEXE%" "%~dp0..\app\lib\bootstrap.py" setup
if errorlevel 1 goto :end
"%LOCALAPPDATA%\BodiesOfTruth\venv\Scripts\python.exe" -c "import tkinter" 2>nul
if errorlevel 1 echo The GUI needs Tkinter: re-run the Python installer, choose Modify and tick "tcl/tk and IDLE". The command-line converter works without it.
if not errorlevel 1 echo Ready. Start BodiesOfTruth_GUI.bat in the tool folder
:end
pause

@echo off
rem SPDX-License-Identifier: GPL-3.0-or-later
rem Copyright (C) 2026 BodiesOfTruth contributors. See LICENSE.txt and CREDITS.txt.
rem Installs the exact package versions the converter was built and tested with.
cd /d "%~dp0"
python -m pip install -r requirements.txt
python -c "import tkinter" 2>nul
if errorlevel 1 echo The GUI needs Tkinter: re-run the Python installer, choose Modify and tick "tcl/tk and IDLE". The command-line converter works without it.
pause

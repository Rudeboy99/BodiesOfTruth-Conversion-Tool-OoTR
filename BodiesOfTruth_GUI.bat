@echo off
rem SPDX-License-Identifier: GPL-3.0-or-later
rem Copyright (C) 2026 BodiesOfTruth contributors. See LICENSE.txt and CREDITS.txt.
rem BodiesOfTruth V1.3 GUI. Double-click, or drag a mod folder onto this file.
cd /d "%~dp0"
python -c "import tkinter" 2>nul
if errorlevel 1 (
  echo Python or its Tkinter part is missing. Run install_requirements.bat first.
  pause
  exit /b 1
)
where pythonw >/dev/null 2>nul
if errorlevel 1 (
  python "%~dp0BodiesOfTruth_GUI.pyw" %*
) else (
  start "" pythonw "%~dp0BodiesOfTruth_GUI.pyw" %*
)

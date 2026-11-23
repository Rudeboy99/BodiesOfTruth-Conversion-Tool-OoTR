@echo off
rem SPDX-License-Identifier: GPL-3.0-or-later
rem Copyright (C) 2026 BodiesOfTruth contributors. See LICENSE.txt and CREDITS.txt.
rem Drag a mod folder (or a pack of mod folders) onto this file.
rem Double-click: asks for the game files (first run only), the platform (1/2/3), then a mod folder.
rem First run also finds (or installs) Python and sets up the tool's packages.
setlocal
cd /d "%~dp0.."
call "%~dp0..\app\lib\find_python.bat" || goto :end
"%PYEXE%" "%~dp0..\app\lib\bootstrap.py" cli %*
:end
pause

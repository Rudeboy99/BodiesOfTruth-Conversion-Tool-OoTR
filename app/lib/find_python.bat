@echo off
rem SPDX-License-Identifier: GPL-3.0-or-later
rem Copyright (C) 2026 BodiesOfTruth contributors. See LICENSE.txt and CREDITS.txt.
rem Used by the launchers: sets PYEXE to a Python 3.10 or newer. If none is found it offers to
rem install Python 3.12 (python.org's installer, through winget), or opens the download page.
set "PYEXE="
call :try py -3
if defined PYEXE exit /b 0
call :try python
if defined PYEXE exit /b 0
for %%V in (314 313 312 311 310) do if not defined PYEXE if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" call :try "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
if defined PYEXE exit /b 0
echo.
echo Python 3.10 or newer was not found. BodiesOfTruth needs it (free, from python.org).
where winget >nul 2>nul
if errorlevel 1 goto :manual
choice /c YN /m "Install Python 3.12 now"
if errorlevel 2 goto :manual
winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
call :try "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if defined PYEXE exit /b 0
call :try py -3
if defined PYEXE exit /b 0
:manual
echo.
echo Install Python 3.12 from python.org (the page opens now). During setup tick
echo "Add python.exe to PATH" and keep "tcl/tk and IDLE" ticked. Then start the tool again.
start "" https://www.python.org/downloads/
exit /b 1

:try
for /f "delims=" %%I in ('call %* -c "import sys; sys.version_info >= (3, 10) and print(sys.executable)" 2^>nul') do set "PYEXE=%%I"
exit /b 0

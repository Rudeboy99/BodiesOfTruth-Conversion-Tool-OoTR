@echo off
rem SPDX-License-Identifier: GPL-3.0-or-later
rem Copyright (C) 2026 BodiesOfTruth contributors. See LICENSE.txt and CREDITS.txt.
rem Drag a mod folder (or a pack of mod folders) onto this file.
cd /d "%~dp0"
rem Double-click: asks for the game files (first run only), then the platform (1/2/3), then for a mod folder.
python BodiesOfTruth.py %*
pause

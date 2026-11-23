#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 BodiesOfTruth contributors. See LICENSE.txt and CREDITS.txt.
# BodiesOfTruth V1.3.1 GUI (Linux). First run sets up the tool's packages by itself.
#   bash BodiesOfTruth_GUI_linux.sh                 opens the window
#   bash BodiesOfTruth_GUI_linux.sh "path/to/mod"   opens it with that mod already chosen
DIR=$(cd "$(dirname "$0")" && pwd) || exit 1
pause() { if [ -t 0 ] && [ -t 1 ]; then read -rp "Press Enter to continue..."; fi; }
command -v python3 >/dev/null || { echo "Python 3 is not installed. Debian/Ubuntu: sudo apt install python3 python3-venv python3-tk"; pause; exit 1; }
ARG=()
[ $# -gt 0 ] && ARG=("$(cd "$(dirname "$1")" 2>/dev/null && pwd)/$(basename "$1")")   # relative paths: from where you are
python3 "$DIR/app/lib/bootstrap.py" gui "${ARG[@]}" || { pause; exit 1; }

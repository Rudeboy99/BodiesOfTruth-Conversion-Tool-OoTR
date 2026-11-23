#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 BodiesOfTruth contributors. See LICENSE.txt and CREDITS.txt.
# Linux launcher. Run it in a terminal (works from any folder; relative paths are taken from where you are):
#   bash BodiesOfTruth_linux.sh                 asks for the game files (first run only), the platform (1/2/3), then a mod folder
#   bash BodiesOfTruth_linux.sh "path/to/mod"   converts that mod (any converter option works here too)
# First run sets up the tool's packages by itself.
DIR=$(cd "$(dirname "$0")/.." && pwd) || exit 1   # the tool folder
command -v python3 >/dev/null || { echo "Python 3 is not installed. Debian/Ubuntu: sudo apt install python3 python3-venv"; exit 1; }
python3 "$DIR/app/lib/bootstrap.py" cli "$@"
status=$?
if [ -t 0 ] && [ -t 1 ]; then read -rp "Press Enter to continue..."; fi   # only when someone is at the terminal
exit $status

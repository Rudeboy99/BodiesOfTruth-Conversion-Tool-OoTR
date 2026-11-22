#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 BodiesOfTruth contributors. See LICENSE.txt and CREDITS.txt.
# Linux launcher. Run it in a terminal (works from any folder; relative paths are taken from where you are):
#   bash BodiesOfTruth_linux.sh                 asks for the game files (first run only), the platform (1/2/3), then a mod folder
#   bash BodiesOfTruth_linux.sh "path/to/mod"   converts that mod (any converter option works here too)
DIR=$(cd "$(dirname "$0")" && pwd) || exit 1
VENV="${XDG_DATA_HOME:-$HOME/.local/share}/BodiesOfTruth/venv"
if [ -x "$VENV/bin/python" ]; then PY="$VENV/bin/python"; else PY=python3; fi
"$PY" "$DIR/BodiesOfTruth.py" "$@"
status=$?
if [ -t 0 ] && [ -t 1 ]; then read -rp "Press Enter to continue..."; fi   # only when someone is at the terminal
exit $status

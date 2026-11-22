#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 BodiesOfTruth contributors. See LICENSE.txt and CREDITS.txt.
# BodiesOfTruth V1.3 GUI (Linux). Uses the same Python environment as BodiesOfTruth_linux.sh.
#   bash BodiesOfTruth_GUI_linux.sh                 opens the window
#   bash BodiesOfTruth_GUI_linux.sh "path/to/mod"   opens it with that mod already chosen
DIR=$(cd "$(dirname "$0")" && pwd) || exit 1
VENV="${XDG_DATA_HOME:-$HOME/.local/share}/BodiesOfTruth/venv"
if [ -x "$VENV/bin/python" ]; then PY="$VENV/bin/python"; else PY=python3; fi
if ! "$PY" -c 'import tkinter' 2>/dev/null; then
    echo "Tkinter is missing for $("$PY" -c 'import sys;print(sys.version.split()[0])'). Run: bash install_requirements_linux.sh"
    echo "(or install it yourself, e.g. Debian/Ubuntu: sudo apt install python3-tk, Fedora: sudo dnf install python3-tkinter, Arch: sudo pacman -S tk)"
    if [ -t 0 ] && [ -t 1 ]; then read -rp "Press Enter to continue..."; fi
    exit 1
fi
ARG=()
[ $# -gt 0 ] && ARG=("$(cd "$(dirname "$1")" 2>/dev/null && pwd)/$(basename "$1")")   # relative paths: from where you are
exec "$PY" "$DIR/BodiesOfTruth_GUI.pyw" "${ARG[@]}"

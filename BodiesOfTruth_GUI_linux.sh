#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 BodiesOfTruth contributors. See LICENSE.txt and CREDITS.txt.
# BodiesOfTruth V1.4 GUI (Linux). First run sets up the tool's packages by itself.
#   double-click (file manager) or: bash BodiesOfTruth_GUI_linux.sh ["path/to/mod"]
# Opened without a terminal (double-click): if setup is done, the window opens straight away; otherwise a
# terminal opens to show the setup or any error, and closes by itself once the window is up.
DIR=$(cd "$(dirname "$0")" && pwd) || exit 1
SELF="$DIR/$(basename "$0")"
ARG=()
[ $# -gt 0 ] && ARG=("$(cd "$(dirname "$1")" 2>/dev/null && pwd)/$(basename "$1")")   # relative paths: from where you are

if [ ! -t 1 ] && [ -z "$BOT_IN_TERMINAL" ]; then
    if command -v python3 >/dev/null && python3 "$DIR/app/lib/bootstrap.py" check gui 2>/dev/null; then
        BOT_DETACH=1 exec python3 "$DIR/app/lib/bootstrap.py" gui "${ARG[@]}"     # ready: no terminal needed
    fi
    # setup to do or an error to show: reopen this launcher in a terminal so the player can see it
    CMD=(env BOT_IN_TERMINAL=1 bash "$SELF" "${ARG[@]}")
    for t in x-terminal-emulator gnome-terminal kgx ptyxis konsole xfce4-terminal mate-terminal lxterminal tilix kitty alacritty wezterm foot xterm; do
        command -v "$t" >/dev/null || continue
        case "$t" in
            gnome-terminal|kgx|ptyxis|tilix) exec "$t" -- "${CMD[@]}" ;;
            xfce4-terminal|mate-terminal)    exec "$t" -x "${CMD[@]}" ;;
            kitty|foot)                      exec "$t" "${CMD[@]}" ;;
            wezterm)                         exec "$t" start -- "${CMD[@]}" ;;
            *)                               exec "$t" -e "${CMD[@]}" ;;
        esac
    done
    MSG="BodiesOfTruth needs a terminal for its first start. Open one in the tool folder and run: bash BodiesOfTruth_GUI_linux.sh"
    command -v zenity >/dev/null && exec zenity --error --text="$MSG"
    command -v kdialog >/dev/null && exec kdialog --error "$MSG"
    command -v notify-send >/dev/null && exec notify-send "BodiesOfTruth" "$MSG"
    exit 1
fi

pause() { if [ -t 0 ] && [ -t 1 ]; then read -rp "Press Enter to close..."; fi; }
command -v python3 >/dev/null || { echo "Python 3 is not installed. Debian/Ubuntu: sudo apt install python3 python3-venv python3-tk"; pause; exit 1; }
if [ -n "$BOT_IN_TERMINAL" ]; then
    # opened by a double-click: set up, open the window on its own, then let this terminal close
    BOT_DETACH=1 python3 "$DIR/app/lib/bootstrap.py" gui "${ARG[@]}" || { pause; exit 1; }
    echo "Opening the BodiesOfTruth window. This terminal closes by itself."; sleep 3; exit 0
fi
python3 "$DIR/app/lib/bootstrap.py" gui "${ARG[@]}" || { pause; exit 1; }

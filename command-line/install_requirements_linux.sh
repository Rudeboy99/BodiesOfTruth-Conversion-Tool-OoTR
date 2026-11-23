#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 BodiesOfTruth contributors. See LICENSE.txt and CREDITS.txt.
# Linux one-time setup. Installs the converter's Python packages into its own environment:
#   ~/.local/share/BodiesOfTruth/venv   (outside the tool folder; nothing is installed system-wide,
#                                        except the venv module below if you agree to it)
# Python 3.12+ gets the exact tested versions from requirements.txt; 3.10/3.11 get numpy 2.2.6
# (also tested; numpy 2.5 needs 3.12). Run it again any time to repair the environment.
# To remove everything it installed: delete ~/.local/share/BodiesOfTruth
DIR=$(cd "$(dirname "$0")/.." && pwd) || exit 1   # the tool folder
VENV="${XDG_DATA_HOME:-$HOME/.local/share}/BodiesOfTruth/venv"
pause() { if [ -t 0 ] && [ -t 1 ]; then read -rp "Press Enter to continue..."; fi; }   # only when someone is at the terminal
fail() { echo "$1"; pause; exit 1; }

[ "$(id -u)" -eq 0 ] && fail "Don't run this with sudo or as root: run it as your normal user (it asks for sudo itself only if needed)."
command -v python3 >/dev/null || fail "Python 3 is not installed. On Debian/Ubuntu:  sudo apt install python3"
PYVER=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' ||
    fail "Python $PYVER found; the converter needs Python 3.10 or newer. Install a newer Python, then run this again."
echo "Using Python $PYVER"

# keep a working environment (a failed download then can't break it); rebuild only a missing or broken one
healthy() { "$VENV/bin/python" -m pip --version >/dev/null 2>&1; }
make_venv() { healthy && return 0; rm -rf "$VENV"; ERR=$(python3 -m venv "$VENV" 2>&1) && healthy; }

if ! make_venv; then
    rm -rf "$VENV"                                       # drop the half-made environment
    PKG="python$PYVER-venv"                              # e.g. python3.14-venv: matches this Python exactly
    if command -v apt-get >/dev/null && echo "$ERR" | grep -qi "ensurepip\|venv"; then
        echo "Python $PYVER needs the package $PKG to create the converter's environment."
        read -rp "Install it now with sudo (asks for your Linux password)? [Y/n] " ok
        if [ "${ok:-y}" != "n" ] && [ "${ok:-y}" != "N" ]; then
            read -rp "Refresh the package lists first (sudo apt-get update)? Recommended unless you just did it. [Y/n] " up
            if [ "${up:-y}" != "n" ] && [ "${up:-y}" != "N" ]; then
                sudo apt-get update || echo "apt-get update failed; trying the install anyway."
            fi
            sudo apt-get install -y "$PKG" || sudo apt-get install -y python3-venv
        fi
    fi
    if ! make_venv; then
        rm -rf "$VENV"
        echo "Could not create the Python environment:"; echo "$ERR" | tail -5
        fail "Install the venv module for Python $PYVER (Debian/Ubuntu: $PKG), then run this again."
    fi
fi

if python3 -c 'import sys; sys.exit(sys.version_info < (3, 12))'; then
    "$VENV/bin/python" -m pip install --disable-pip-version-check -r "$DIR/app/requirements.txt"
else
    echo "Python $PYVER: installing numpy 2.2.6 (the newest tested version for this Python; numpy 2.5.4 needs 3.12+)."
    "$VENV/bin/python" -m pip install --disable-pip-version-check "numpy==2.2.6" "zstandard==0.25.0"
fi || fail "Package install failed (see above). Check your internet connection, then run this again."

# the GUI (BodiesOfTruth_GUI_linux.sh) needs Tkinter; the command-line converter works without it
if ! "$VENV/bin/python" -c 'import tkinter' 2>/dev/null; then
    echo "The GUI needs Tkinter, which is missing for Python $PYVER (the command-line converter works without it)."
    if command -v apt-get >/dev/null; then
        read -rp "Install python3-tk now with sudo? [Y/n] " ok
        if [ "${ok:-y}" != "n" ] && [ "${ok:-y}" != "N" ]; then sudo apt-get install -y python3-tk; fi
    elif command -v dnf >/dev/null; then echo "Install it with:  sudo dnf install python3-tkinter"
    elif command -v pacman >/dev/null; then echo "Install it with:  sudo pacman -S tk"
    elif command -v zypper >/dev/null; then echo "Install it with:  sudo zypper install python3-tk"
    else echo "Install your distribution's Tkinter package for Python $PYVER."; fi
    "$VENV/bin/python" -c 'import tkinter' 2>/dev/null && echo "Tkinter OK."
fi

python3 "$DIR/app/lib/bootstrap.py" setup >/dev/null || echo "Note: lib/bootstrap.py could not record the setup; the launchers will redo it on first start."
echo "Done. Installed into $VENV (delete ~/.local/share/BodiesOfTruth to remove it)."
echo "Run:  bash BodiesOfTruth_GUI_linux.sh   (window)   or   bash command-line/BodiesOfTruth_linux.sh   (command line)"
pause

# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 BodiesOfTruth contributors. See LICENSE.txt and CREDITS.txt.
"""First-run setup used by every launcher (Windows and Linux alike).

  python app/lib/bootstrap.py gui   [mod folder]       set up if needed, then open the GUI
  python app/lib/bootstrap.py cli   [converter args]   set up if needed, then run BodiesOfTruth.py in this console
  python app/lib/bootstrap.py setup                    set up (or repair) only
  python app/lib/bootstrap.py check [gui]              exit 0 if set up (and, with gui, Tkinter works); prints nothing

Setup = the tool's own Python environment outside the tool folder, with the tested package versions:
  Windows  %LOCALAPPDATA%\\BodiesOfTruth\\venv
  Linux    ~/.local/share/BodiesOfTruth/venv   (same place install_requirements_linux.sh uses)
Done once; later runs only check it (well under a second) and start the tool. Uses only the standard library,
so it runs on any Python 3.10+ before anything is installed. Delete the BodiesOfTruth folder above to undo it."""
import os, sys, subprocess, json, shutil

TOOL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # app/
REQS = os.path.join(TOOL, 'requirements.txt')
MIN_PY = (3, 10)
FALLBACK = ['numpy==2.2.6', 'zstandard==0.25.0']     # tested on Python 3.10/3.11 (numpy 2.5 needs 3.12+)
WIN = os.name == 'nt'


def say(msg=''): print(msg, flush=True)

def fail(msg):
    say(''); say('!! ' + msg)
    sys.exit(1)

def env_dir():
    if WIN: base = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~\\AppData\\Local')
    else: base = os.environ.get('XDG_DATA_HOME') or os.path.expanduser('~/.local/share')
    return os.path.join(base, 'BodiesOfTruth', 'venv')

def env_python(windowed=False):
    d = env_dir()
    if WIN: return os.path.join(d, 'Scripts', 'pythonw.exe' if windowed else 'python.exe')
    return os.path.join(d, 'bin', 'python')

def wanted():
    """the package list for the Python the environment is built from"""
    if sys.version_info >= (3, 12):
        try: return [l.strip() for l in open(REQS, encoding='utf-8') if l.strip() and not l.startswith('#')]
        except OSError: pass
    return list(FALLBACK)

def marker(): return os.path.join(os.path.dirname(env_dir()), 'installed.json')

def run_quiet(cmd):
    try: return subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    except OSError: return False

def ready(pkgs):
    """environment exists, works, and holds exactly what this tool version wants"""
    py = env_python()
    if not os.path.isfile(py): return False
    try: m = json.load(open(marker(), encoding='utf-8'))
    except (OSError, ValueError): m = {}
    if m.get('packages') != pkgs: return False
    return run_quiet([py, '-c', 'import numpy, zstandard'])

def make_env():
    d = env_dir(); py = env_python()
    if os.path.isfile(py) and run_quiet([py, '-m', 'pip', '--version']): return
    say('Creating the tool\'s Python environment in ' + d)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(os.path.dirname(d), exist_ok=True)
    r = subprocess.run([sys.executable, '-m', 'venv', d], capture_output=True, text=True)
    if r.returncode != 0 or not run_quiet([py, '-m', 'pip', '--version']):
        shutil.rmtree(d, ignore_errors=True)
        err = (r.stderr or r.stdout or '').strip().splitlines()[-3:]
        if WIN: fail('Could not create the environment:\n   ' + '\n   '.join(err) +
                     '\nRe-run the Python installer, choose Repair, then start the tool again.')
        fail('Could not create the environment:\n   ' + '\n   '.join(err) +
             '\nYour Linux needs the Python "venv" package. Run once:  bash command-line/install_requirements_linux.sh\n'
             '(it installs it for you, asking for your password), then start the tool again.')

def setup():
    if sys.version_info < MIN_PY:
        fail('Python %d.%d found; the tool needs Python %d.%d or newer.' % (sys.version_info[:2] + MIN_PY))
    pkgs = wanted()
    if ready(pkgs): return
    say('=' * 66); say('  BodiesOfTruth first-time setup (one time only, about a minute)'); say('=' * 66)
    make_env()
    say('Installing: ' + ', '.join(pkgs))
    r = subprocess.run([env_python(), '-m', 'pip', 'install', '--disable-pip-version-check', '--no-input'] + pkgs)
    if r.returncode != 0 or not run_quiet([env_python(), '-c', 'import numpy, zstandard']):
        fail('Package install failed (see above). Check your internet connection, then start the tool again.')
    json.dump({'packages': pkgs, 'python': sys.version.split()[0]}, open(marker(), 'w', encoding='utf-8'))
    say('Setup done.'); say('')

def tk_missing_help():
    if WIN: return ('Tkinter (the window toolkit) is missing from your Python. Re-run the Python installer, '
                    'choose Modify, tick "tcl/tk and IDLE", then start the tool again.')
    return ('Tkinter (the window toolkit) is missing. Install it once, then start the tool again:\n'
            '   Debian/Ubuntu: sudo apt install python3-tk    Fedora: sudo dnf install python3-tkinter\n'
            '   Arch: sudo pacman -S tk    (or run: bash command-line/install_requirements_linux.sh)')

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'setup'
    args = sys.argv[2:]
    if mode == 'check':          # used by the Linux launcher to decide whether a terminal is needed
        ok = sys.version_info >= MIN_PY and ready(wanted())
        if ok and 'gui' in args: ok = run_quiet([env_python(), '-c', 'import tkinter; tkinter.Tcl()'])
        sys.exit(0 if ok else 1)
    setup()
    if mode == 'setup': return
    if mode == 'cli':
        sys.exit(subprocess.call([env_python(), os.path.join(TOOL, 'BodiesOfTruth.py')] + args))
    if mode == 'gui':
        if not run_quiet([env_python(), '-c', 'import tkinter; tkinter.Tcl()']): fail(tk_missing_help())
        gui = os.path.join(TOOL, 'BodiesOfTruth_GUI.pyw')
        if WIN:   # windowed Python, detached: the console window can close
            subprocess.Popen([env_python(windowed=True), gui] + args, cwd=TOOL, close_fds=True,
                             creationflags=0x00000008 | 0x00000200)   # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
            return
        if os.environ.get('BOT_DETACH'):   # opened by a double-click: the window lives on after the launcher exits
            subprocess.Popen([env_python(), gui] + args, cwd=TOOL, start_new_session=True,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        os.execv(env_python(), [env_python(), gui] + args)
    fail('unknown mode: ' + mode)


if __name__ == '__main__':
    main()

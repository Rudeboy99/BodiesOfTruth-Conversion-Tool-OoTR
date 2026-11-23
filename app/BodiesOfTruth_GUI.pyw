#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 BodiesOfTruth contributors. See LICENSE.txt and CREDITS.txt.
"""BodiesOfTruth V1.3.3 GUI: a window around the BodiesOfTruth converter (BodiesOfTruth.py).

The GUI does no converting itself. It runs BodiesOfTruth.py with the options picked in the window, shows its output
live, and reads the converted mod's manifest (bodiesoftruth_manifest.json) and report (BodiesOfTruth_report.txt) to show
what the converted mod contains. Everything it writes goes through the converter, so the output is the same as from the
command line.

  Windows: double-click BodiesOfTruth_GUI.bat (or drag a mod folder onto it)
  Linux:   bash BodiesOfTruth_GUI_linux.sh
Both set up Python packages by themselves on first run (lib/bootstrap.py).
"""
import os, sys, json, glob, re, subprocess, threading, queue, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib'))
import gamefiles                           # the converter's own game-files finder (standard library only)
sys.dont_write_bytecode = True            # no __pycache__ in the tool folder (it would embed this PC's folder paths)

GUI_VERSION = 'BodiesOfTruth V1.3.3'
HERE = os.path.dirname(os.path.abspath(__file__))          # app/: the program files
ROOT = os.path.dirname(HERE)                                # the tool's top folder: settings.json, Converted
CONVERTER = os.path.join(HERE, 'BodiesOfTruth.py')
SETTINGS = os.path.join(ROOT, 'settings.json')
CONVERTED = os.path.join(ROOT, 'Converted')
INDEX = os.path.join(HERE, 'index', 'npc_index.json')
DEFAULT_NAME = 'BodiesOfTruth - Custom'
LENS_NAME = 'LensPatch'
LENS_INFO = 'LensPatch_info.txt'
MANIFEST = 'bodiesoftruth_manifest.json'
REPORT = 'BodiesOfTruth_report.txt'
RESTBL = 'System/Resource/ResourceSizeTable.Product.111.Nin_Ounce_NVN2.rsizetable.zs'
# same keys, labels and lens files as PLATFORMS in BodiesOfTruth.py
PLATFORMS = [('emulation', 'Emulation (Fritchii)', 'lens code as its own module: LensPatch/exefs/subsdk1 + IPS'),
             ('recomp', 'Recomp (Hookshot/Longshot)', 'lens code in the code cave: LensPatch/exefs IPS'),
             ('native', 'Native (Official Hardware)', 'lens code in the code cave: LensPatch/exefs IPS + pchtxt')]
PLATFORM_LABEL = {k: l for k, l, _ in PLATFORMS}
DROP_HINT = ('Drop a folder on BodiesOfTruth_GUI.bat, or paste its path.' if os.name == 'nt' else
             'Paste its path (or start: bash BodiesOfTruth_GUI_linux.sh "path/to/mod").')
PLATFORM_WARN = {'native': 'Not yet tested on native hardware'}
TOGETHER_NOTE = ('Be sure to convert all intended conversion mods together. This tool generates a unified RESTBL and '
                 'code patch to avoid conflicts. You may merge this mod with others after your unified folder is '
                 'generated (Untested).')
ANSI = re.compile(r'\033\[(\d+)m')


# ------------------------------------------------------------------ helpers (no Tk needed: testable headless)
def load_settings():
    try: return json.load(open(SETTINGS, encoding='utf-8'))
    except (OSError, ValueError): return {}

def save_settings(**kw):
    """settings.json is shared with the command-line converter (it reads 'game_files'); the GUI adds its own keys"""
    s = load_settings(); s.update({k: v for k, v in kw.items() if v is not None})
    try: json.dump(s, open(SETTINGS, 'w', encoding='utf-8'), indent=1)
    except OSError: pass

def clean_path(t):
    """a typed, pasted or dropped path -> plain path, with the same rules as clean_path() in BodiesOfTruth.py:
    "quotes" (Windows Copy as path), 'quotes' and back\\ slashed spaces (Linux terminals), file:// links, ~"""
    t = (t or '').strip()
    if t.startswith('{') and t.endswith('}'): t = t[1:-1]          # Tk drag-and-drop wraps paths with spaces
    if t.startswith('file://'):
        from urllib.parse import unquote; t = unquote(t[7:])
    elif os.name != 'nt' and (t[:1] in '"\'' or '\\' in t):
        import shlex
        try: t = ' '.join(shlex.split(t))
        except ValueError: t = t.strip('"\'')
    else: t = t.strip('"')
    return os.path.expanduser(t)

def rel_show(p):
    """a path inside the tool folder as the platform writes it: Converted\\X on Windows, Converted/X on Linux"""
    return os.path.join(*p.split('/'))

def check_game_files(g):
    """(ok, message): the same search as the converter (lib/gamefiles.py), plus .nup game files"""
    if not g: return False, 'not set'
    g = os.path.abspath(g)
    if os.path.isfile(g) and g.lower().endswith('.nup'): return True, '.nup game file (conversion may be slower)'
    p, msg = gamefiles.find_game_romfs(g)
    if p: return True, '%s: %s' % (msg, gamefiles.describe(p))
    if os.path.isdir(g) and len(glob.glob(os.path.join(glob.escape(g), '*.nup'))) == 1: return True, '.nup game file (conversion may be slower)'
    return False, msg

def find_romfs(inp):
    """same discovery as BodiesOfTruth.py: the input itself, or every romfs folder up to 4 levels down"""
    inp = os.path.abspath(inp)
    if os.path.isdir(os.path.join(inp, 'Model')) or os.path.basename(inp).lower() == 'romfs': return [inp]
    out = []
    for root, dirs, files in os.walk(inp):
        if os.path.basename(root).lower() == 'romfs': out.append(root); dirs[:] = []
        elif root[len(inp):].count(os.sep) >= 4: dirs[:] = []
    return sorted(out)

def mod_name(rd):
    rd = os.path.abspath(rd)
    return os.path.basename(os.path.dirname(rd)) if os.path.basename(rd).lower() == 'romfs' else os.path.basename(rd)

_index_models = None
def index_models():
    global _index_models
    if _index_models is None:
        try: _index_models = set(json.load(open(INDEX, encoding='utf-8')).get('models', {}))
        except (OSError, ValueError): _index_models = set()
    return _index_models

def preview_input(inp):
    """[(mod name, [model keys], n other files)] for an input folder: a quick look before converting"""
    res = []
    if not inp or not os.path.isdir(inp): return res
    for rd in find_romfs(inp):
        models, other = [], 0
        for root, _, files in os.walk(rd):
            for f in files:
                rel = os.path.relpath(os.path.join(root, f), rd).replace(os.sep, '/')
                if rel.startswith('Model/') and f.endswith('.bfres.zs') and '.anim.' not in f and '.Skeleton.' not in f:
                    models.append(f[:-9])
                else: other += 1
        res.append((mod_name(rd), sorted(models), other))
    return res

def output_dir(name): return os.path.join(CONVERTED, name or DEFAULT_NAME)
def lens_dir(name): return os.path.join(CONVERTED, LENS_NAME)

def converted_folders():
    try: names = sorted(d for d in os.listdir(CONVERTED) if os.path.isdir(os.path.join(CONVERTED, d)) and d != LENS_NAME)
    except OSError: names = []
    return names if DEFAULT_NAME in names else [DEFAULT_NAME] + names

def read_manifest(name):
    p = os.path.join(output_dir(name), MANIFEST)
    try: return json.load(open(p, encoding='utf-8'))
    except (OSError, ValueError): return None

def read_report(name):
    try: return open(os.path.join(output_dir(name), REPORT), encoding='utf-8').read()
    except OSError: return ''

def report_sections(text):
    """{model key: its '== key' block} from a report"""
    out, key, buf = {}, None, []
    for line in text.splitlines():
        if line.startswith('== '):
            if key: out[key] = '\n'.join(buf).rstrip()
            key, buf = line[3:].strip(), [line]
        elif key is not None:
            if not line.strip() and buf and not buf[-1].strip(): continue
            if line and not line.startswith(' ') and not line.startswith('=='):
                out[key] = '\n'.join(buf).rstrip(); key, buf = None, []; continue
            buf.append(line)
    if key: out[key] = '\n'.join(buf).rstrip()
    return out

def lens_status(name):
    """(platform label or None, [exefs files], info text) for the LensPatch folder"""
    ld = lens_dir(name); man = read_manifest(name) or {}
    files = sorted(os.listdir(os.path.join(ld, 'exefs'))) if os.path.isdir(os.path.join(ld, 'exefs')) else []
    try: info = open(os.path.join(ld, LENS_INFO), encoding='utf-8').read()
    except OSError: info = ''
    plat = man.get('platform')
    m = re.search(r'^platform: (.+)$', info, re.M)
    label = PLATFORM_LABEL.get(plat) or (m.group(1).strip() if m else None)
    return (label if files else None), files, info

def python_for_child():
    """python.exe for the converter even when the GUI runs under pythonw.exe (so its output can be read)"""
    exe = sys.executable or 'python'
    d, b = os.path.split(exe)
    if b.lower().startswith('pythonw'):
        alt = os.path.join(d, b.lower().replace('pythonw', 'python'))
        if os.path.isfile(alt): return alt
    return exe

def build_command(action, game_files, platform, name, inp=None, dry_run=False, keep_cloth=False, no_patch=False, remove=None):
    """the BodiesOfTruth.py command line for one GUI action ('convert', 'remove' or 'list')"""
    cmd = [python_for_child(), '-u', CONVERTER]
    if action == 'convert': cmd.append(inp)
    elif action == 'remove': cmd += ['--remove', remove]
    elif action == 'list': cmd.append('--list')
    if name and name != DEFAULT_NAME: cmd += ['--name', name]
    if game_files: cmd += ['--game-files', game_files]
    if platform and action != 'list': cmd += ['--platform', platform]   # always given: the converter must never ask
    if action == 'convert':
        if dry_run: cmd.append('--dry-run')
        if keep_cloth: cmd.append('--keep-cloth-weights')
    if no_patch and action != 'list': cmd.append('--no-patch')
    return cmd

def start_process(cmd):
    env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1')
    kw = {}
    if os.name == 'nt': kw['creationflags'] = 0x08000000           # CREATE_NO_WINDOW
    # stdin closed: if the converter ever asks a question it fails at once instead of hanging the window
    return subprocess.Popen(cmd, cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', bufsize=1, **kw)

def split_ansi(line, colour=None):
    """([(text, colour code or None)], colour at the end) for a converter output line. It colours with \\033[91m red
    and \\033[92m green, sometimes starting on one line and resetting on the next, so the colour carries over
    (like a terminal)"""
    parts, pos = [], 0
    for m in ANSI.finditer(line):
        if m.start() > pos: parts.append((line[pos:m.start()], colour))
        colour = None if m.group(1) == '0' else m.group(1); pos = m.end()
    if pos < len(line): parts.append((line[pos:], colour))
    return parts, colour

def pick_font(root, names):
    """first installed font family from names (Windows and Linux ship different ones)"""
    try:
        from tkinter import font as tkfont
        have = {f.lower() for f in tkfont.families(root)}
        return next((n for n in names if n.lower() in have), 'TkDefaultFont')
    except Exception: return names[-1]

def open_path(p):
    if not os.path.exists(p): return False
    if os.name == 'nt': os.startfile(p)                            # noqa
    elif sys.platform == 'darwin': subprocess.Popen(['open', p])
    else: subprocess.Popen(['xdg-open', p])
    return True


# ------------------------------------------------------------------ window
try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
except ImportError:
    tk = None

if tk:
    C = dict(bg='#1c2026', panel='#242a32', field='#2d343e', line='#38414d', fg='#dfe5ec', dim='#8d99a8',
             accent='#c9a44c', accent2='#7ba7d9', red='#f07070', green='#7fd18b', logbg='#14171b')

    class App:
        def __init__(self, root, initial_input=None):
            self.root = root; self.proc = None; self.q = queue.Queue(); self.action = None
            s = load_settings()
            root.title('%s  -  Lens Outfit Converter' % GUI_VERSION)
            root.geometry(s.get('gui_geometry') or '1180x780'); root.minsize(980, 640)
            root.configure(bg=C['bg'])
            self.style()
            self.v_game = tk.StringVar(value=s.get('game_files', ''))
            self.v_platform = tk.StringVar(value=s.get('gui_platform', 'emulation'))
            self.v_input = tk.StringVar(value=initial_input or s.get('gui_last_input', ''))
            self.v_name = tk.StringVar(value=s.get('gui_output_name', DEFAULT_NAME))
            self.v_dry = tk.BooleanVar(value=False)
            self.v_cloth = tk.BooleanVar(value=False)
            self.v_nopatch = tk.BooleanVar(value=False)
            self.v_status = tk.StringVar(value='Ready')
            self.build()
            self.v_game.trace_add('write', lambda *a: self.schedule_game_check())
            self.v_input.trace_add('write', lambda *a: self.schedule_preview())
            self.v_name.trace_add('write', lambda *a: self.refresh_converted())
            self.v_platform.trace_add('write', lambda *a: self.update_platform_note())
            self.update_game_status(); self.update_platform_note(); self.refresh_preview(); self.refresh_converted()
            root.protocol('WM_DELETE_WINDOW', self.on_close)
            root.after(80, self.poll)
            root.after(300, self.check_packages)
            self.enable_drop()

        # ---------------- look
        def style(self):
            st = ttk.Style(self.root); st.theme_use('clam')
            f = (pick_font(self.root, ('Segoe UI', 'Noto Sans', 'DejaVu Sans', 'Liberation Sans', 'Helvetica')), 10)
            self.font = f; self.mono = (pick_font(self.root, ('Consolas', 'DejaVu Sans Mono', 'Noto Sans Mono', 'Liberation Mono', 'Courier')), 9)
            from tkinter import font as tkfont
            row = tkfont.Font(root=self.root, family=f[0], size=f[1]).metrics('linespace') + 6   # follows DPI on both systems
            st.configure('.', background=C['bg'], foreground=C['fg'], fieldbackground=C['field'], bordercolor=C['line'],
                         lightcolor=C['line'], darkcolor=C['line'], troughcolor=C['panel'], font=f, focuscolor=C['accent'])
            st.configure('TFrame', background=C['bg']); st.configure('Panel.TFrame', background=C['panel'])
            st.configure('TLabel', background=C['bg']); st.configure('Panel.TLabel', background=C['panel'])
            st.configure('Dim.TLabel', background=C['panel'], foreground=C['dim'])
            st.configure('Head.TLabel', background=C['panel'], foreground=C['accent'], font=(f[0], 10, 'bold'))
            st.configure('Title.TLabel', background=C['bg'], foreground=C['fg'], font=(f[0], 17, 'bold'))
            st.configure('Ver.TLabel', background=C['accent'], foreground='#1c2026', font=(f[0], 10, 'bold'), padding=(8, 2))
            st.configure('Sub.TLabel', background=C['bg'], foreground=C['dim'])
            st.configure('Ok.TLabel', background=C['panel'], foreground=C['green'])
            st.configure('Bad.TLabel', background=C['panel'], foreground=C['red'])
            st.configure('Warn.TLabel', background=C['panel'], foreground=C['red'], wraplength=330)
            st.configure('TEntry', fieldbackground=C['field'], foreground=C['fg'], insertcolor=C['fg'], padding=4)
            st.configure('TCombobox', fieldbackground=C['field'], foreground=C['fg'], arrowcolor=C['fg'], background=C['field'], padding=3)
            st.map('TCombobox', fieldbackground=[('readonly', C['field'])], foreground=[('readonly', C['fg'])])
            self.root.option_add('*TCombobox*Listbox.background', C['field'])
            self.root.option_add('*TCombobox*Listbox.foreground', C['fg'])
            st.configure('TButton', background=C['field'], foreground=C['fg'], padding=(10, 4), borderwidth=1)
            st.map('TButton', background=[('disabled', C['panel']), ('active', C['line'])], foreground=[('disabled', C['dim'])])
            st.configure('Go.TButton', background=C['accent'], foreground='#1c2026', font=(f[0], 11, 'bold'), padding=(18, 7))
            st.map('Go.TButton', background=[('disabled', C['line']), ('active', '#ddb95e')], foreground=[('disabled', C['dim'])])
            st.configure('Stop.TButton', padding=(14, 7))
            for w in ('TRadiobutton', 'TCheckbutton'):
                st.configure(w, background=C['panel'], foreground=C['fg'], indicatorbackground=C['field'], indicatorforeground=C['accent'])
                st.map(w, background=[('active', C['panel'])], indicatorbackground=[('selected', C['field'])])
            st.configure('TNotebook', background=C['bg'], borderwidth=0, tabmargins=(0, 4, 0, 0))
            st.configure('TNotebook.Tab', background=C['panel'], foreground=C['dim'], padding=(14, 5))
            st.map('TNotebook.Tab', background=[('selected', C['field'])], foreground=[('selected', C['fg'])])
            st.configure('Treeview', background=C['logbg'], fieldbackground=C['logbg'], foreground=C['fg'], rowheight=row, borderwidth=0)
            st.map('Treeview', background=[('selected', '#3b4a5e')], foreground=[('selected', C['fg'])])
            st.configure('Treeview.Heading', background=C['field'], foreground=C['dim'], relief='flat')
            st.configure('Horizontal.TProgressbar', background=C['accent'], troughcolor=C['field'])

        def panel(self, parent, title):
            fr = ttk.Frame(parent, style='Panel.TFrame', padding=(12, 7, 12, 9))
            ttk.Label(fr, text=title.upper(), style='Head.TLabel').grid(row=0, column=0, columnspan=4, sticky='w', pady=(0, 4))
            fr.columnconfigure(0, weight=1)
            return fr

        def textbox(self, parent, **kw):
            kw.setdefault('wrap', 'word')
            t = tk.Text(parent, bg=C['logbg'], fg=C['fg'], insertbackground=C['fg'], relief='flat',
                        font=self.mono, padx=8, pady=6, borderwidth=0, highlightthickness=0, **kw)
            sb = ttk.Scrollbar(parent, orient='vertical', command=t.yview); t.configure(yscrollcommand=sb.set)
            t.tag_configure('91', foreground=C['red']); t.tag_configure('92', foreground=C['green'])
            t.tag_configure('dim', foreground=C['dim']); t.tag_configure('head', foreground=C['accent'])
            t.tag_configure('cmd', foreground=C['accent2'])
            return t, sb

        # ---------------- layout
        def build(self):
            r = self.root
            top = ttk.Frame(r, padding=(16, 12, 16, 6)); top.pack(fill='x')
            ttk.Label(top, text='Bodies of Truth', style='Title.TLabel').pack(side='left')
            ttk.Label(top, text='V1.3.3', style='Ver.TLabel').pack(side='left', padx=(10, 0), pady=(4, 0))
            ttk.Label(top, text='   NPC outfit mod  ->  second outfit seen only through the Lens of Truth',
                      style='Sub.TLabel').pack(side='left', pady=(5, 0))

            body = ttk.Frame(r, padding=(16, 4, 16, 0)); body.pack(fill='both', expand=True)
            body.columnconfigure(1, weight=1); body.rowconfigure(0, weight=1)
            left = ttk.Frame(body, width=380); left.grid(row=0, column=0, sticky='nsw', padx=(0, 12))
            right = ttk.Frame(body); right.grid(row=0, column=1, sticky='nsew')

            # game files
            p = self.panel(left, 'Game files (update 131072)'); p.pack(fill='x', pady=(0, 6))
            ttk.Entry(p, textvariable=self.v_game, width=26).grid(row=1, column=0, sticky='ew')
            ttk.Button(p, text='Folder', width=7, command=self.pick_game).grid(row=1, column=1, padx=(6, 0))
            ttk.Button(p, text='.nup', width=5, command=self.pick_nup).grid(row=1, column=2, padx=(4, 0))
            self.l_game = ttk.Label(p, text='', style='Dim.TLabel', wraplength=330, justify='left'); self.l_game.grid(row=2, column=0, columnspan=3, sticky='w', pady=(5, 0))

            # platform
            p = self.panel(left, 'Platform'); p.pack(fill='x', pady=(0, 6))
            for i, (k, label, desc) in enumerate(PLATFORMS):
                ttk.Radiobutton(p, text=label, value=k, variable=self.v_platform).grid(row=1 + i, column=0, sticky='w', pady=1)
            self.l_plat = ttk.Label(p, text='', style='Dim.TLabel', wraplength=320, justify='left')
            self.l_plat.grid(row=4, column=0, sticky='w', pady=(3, 0))

            # input
            p = self.panel(left, 'Mod to convert'); p.pack(fill='x', pady=(0, 6))
            ttk.Entry(p, textvariable=self.v_input, width=32).grid(row=1, column=0, sticky='ew')
            ttk.Button(p, text='Browse', width=7, command=self.pick_input).grid(row=1, column=1, padx=(6, 0))
            ttk.Label(p, text='A mod folder (with romfs) or a folder of several mods. ' + DROP_HINT,
                      style='Dim.TLabel', wraplength=320, justify='left').grid(row=2, column=0, columnspan=2, sticky='w', pady=(3, 3))
            self.t_prev, sbp = self.textbox(p, height=5, width=40)
            self.t_prev.grid(row=3, column=0, columnspan=2, sticky='ew'); sbp.grid(row=3, column=2, sticky='ns')

            # output + options
            p = self.panel(left, 'Output'); p.pack(fill='x', pady=(0, 6))
            ttk.Label(p, text='Model folder in ' + rel_show('Converted/'), style='Dim.TLabel').grid(row=1, column=0, sticky='w')
            self.cb_name = ttk.Combobox(p, textvariable=self.v_name, values=converted_folders(), width=30)
            self.cb_name.grid(row=2, column=0, columnspan=2, sticky='ew', pady=(2, 6))
            ttk.Checkbutton(p, text='Dry run (preview only, write nothing)', variable=self.v_dry).grid(row=3, column=0, sticky='w')
            ttk.Checkbutton(p, text='Keep cloth weights (vanilla cloth physics)', variable=self.v_cloth).grid(row=4, column=0, sticky='w')
            ttk.Checkbutton(p, text="Don't write the lens code patch (LensPatch)", variable=self.v_nopatch).grid(row=5, column=0, sticky='w')

            bar = ttk.Frame(left); bar.pack(fill='x', pady=(4, 0))
            self.b_go = ttk.Button(bar, text='Convert', style='Go.TButton', command=self.convert); self.b_go.pack(side='left')
            self.b_stop = ttk.Button(bar, text='Stop', style='Stop.TButton', command=self.stop, state='disabled'); self.b_stop.pack(side='left', padx=8)

            # right: tabs
            self.nb = ttk.Notebook(right); self.nb.pack(fill='both', expand=True)
            # tab: output log
            tl = ttk.Frame(self.nb, style='Panel.TFrame', padding=8); self.nb.add(tl, text='Converter output')
            tl.rowconfigure(1, weight=1); tl.columnconfigure(0, weight=1)
            note = ttk.Label(tl, text=TOGETHER_NOTE, style='Warn.TLabel'); self.autowrap(note)
            note.grid(row=0, column=0, columnspan=2, sticky='ew', pady=(0, 6))
            self.t_log, sbl = self.textbox(tl, state='disabled'); self.t_log.grid(row=1, column=0, sticky='nsew'); sbl.grid(row=1, column=1, sticky='ns')
            lb = ttk.Frame(tl, style='Panel.TFrame'); lb.grid(row=2, column=0, columnspan=2, sticky='ew', pady=(6, 0))
            ttk.Button(lb, text='Clear', command=self.clear_log).pack(side='left')
            ttk.Button(lb, text='Copy all', command=self.copy_log).pack(side='left', padx=6)

            # tab: converted mod
            tc = ttk.Frame(self.nb, style='Panel.TFrame', padding=8); self.nb.add(tc, text='Converted mod')
            tc.columnconfigure(0, weight=1); tc.rowconfigure(2, weight=3); tc.rowconfigure(4, weight=2)
            self.l_out = ttk.Label(tc, text='', style='Panel.TLabel'); self.l_out.grid(row=0, column=0, sticky='ew'); self.autowrap(self.l_out)
            self.l_lens = ttk.Label(tc, text='', style='Dim.TLabel'); self.l_lens.grid(row=1, column=0, sticky='ew', pady=(2, 6)); self.autowrap(self.l_lens)
            tf = ttk.Frame(tc, style='Panel.TFrame'); tf.grid(row=2, column=0, sticky='nsew'); tf.columnconfigure(0, weight=1); tf.rowconfigure(0, weight=1)
            self.tree = ttk.Treeview(tf, columns=('mod', 'built', 'files'), show='tree headings', selectmode='extended')
            self.tree.heading('#0', text='Model'); self.tree.heading('mod', text='From mod'); self.tree.heading('built', text='Built'); self.tree.heading('files', text='Files')
            self.tree.column('#0', width=300, minwidth=160, stretch=True); self.tree.column('mod', width=170, minwidth=90, stretch=True)
            self.tree.column('built', width=136, minwidth=136, stretch=False, anchor='center'); self.tree.column('files', width=46, minwidth=46, stretch=False, anchor='center')
            sbt = ttk.Scrollbar(tf, orient='vertical', command=self.tree.yview); self.tree.configure(yscrollcommand=sbt.set)
            self.tree.grid(row=0, column=0, sticky='nsew'); sbt.grid(row=0, column=1, sticky='ns')
            self.tree.bind('<<TreeviewSelect>>', lambda e: self.show_detail())
            cb = ttk.Frame(tc, style='Panel.TFrame'); cb.grid(row=3, column=0, sticky='ew', pady=6)
            ttk.Button(cb, text='Refresh', command=self.refresh_converted).pack(side='left')
            self.b_remove = ttk.Button(cb, text='Remove selected', command=self.remove_selected); self.b_remove.pack(side='left', padx=6)
            ttk.Button(cb, text='Open Converted folder', command=lambda: self.open(CONVERTED)).pack(side='left')
            df = ttk.Frame(tc, style='Panel.TFrame'); df.grid(row=4, column=0, sticky='nsew'); df.columnconfigure(0, weight=1); df.rowconfigure(0, weight=1)
            self.t_detail, sbd = self.textbox(df, state='disabled'); self.t_detail.grid(row=0, column=0, sticky='nsew'); sbd.grid(row=0, column=1, sticky='ns')

            # tab: report
            tr = ttk.Frame(self.nb, style='Panel.TFrame', padding=8); self.nb.add(tr, text='Last report')
            tr.rowconfigure(0, weight=1); tr.columnconfigure(0, weight=1)
            self.t_report, sbr = self.textbox(tr, state='disabled', wrap='none'); self.t_report.grid(row=0, column=0, sticky='nsew'); sbr.grid(row=0, column=1, sticky='ns')

            # status bar
            sb = ttk.Frame(r, style='Panel.TFrame', padding=(16, 5)); sb.pack(fill='x', side='bottom', pady=(8, 0))
            self.pb = ttk.Progressbar(sb, mode='indeterminate', length=140); self.pb.pack(side='right')
            ttk.Label(sb, textvariable=self.v_status, style='Panel.TLabel').pack(side='left')

        # ---------------- small updates
        def autowrap(self, label):
            label.bind('<Configure>', lambda e: label.configure(wraplength=max(200, e.width - 4)))

        def set_text(self, t, s):
            t.configure(state='normal'); t.delete('1.0', 'end'); t.insert('end', s); t.configure(state='disabled')

        def schedule_game_check(self):
            if getattr(self, '_game_job', None): self.root.after_cancel(self._game_job)
            self.l_game.configure(text='checking...', style='Dim.TLabel')
            self._game_job = self.root.after(450, self.update_game_status)

        def update_game_status(self):
            self._game_job = None
            ok, msg = check_game_files(clean_path(self.v_game.get()))
            self.l_game.configure(text=('OK: ' if ok else 'X  ') + msg, style='Ok.TLabel' if ok else 'Bad.TLabel')
            return ok

        def update_platform_note(self):
            k = self.v_platform.get(); desc = next((d for kk, _, d in PLATFORMS if kk == k), '')
            if k in PLATFORM_WARN: self.l_plat.configure(text=PLATFORM_WARN[k] + '. ' + desc, style='Bad.TLabel')
            else: self.l_plat.configure(text=desc, style='Dim.TLabel')

        def schedule_preview(self):
            if getattr(self, '_prev_job', None): self.root.after_cancel(self._prev_job)
            self._prev_job = self.root.after(350, self.refresh_preview)

        def refresh_preview(self):
            self._prev_job = None
            inp = clean_path(self.v_input.get()); t = self.t_prev
            t.configure(state='normal'); t.delete('1.0', 'end')
            if not inp: t.insert('end', 'No mod chosen yet.', 'dim')
            elif not os.path.isdir(inp): t.insert('end', 'Folder not found.', '91')
            else:
                mods = preview_input(inp); known = index_models(); total = 0
                if not mods: t.insert('end', 'No romfs folder found in here.', '91')
                for name, models, other in mods:
                    t.insert('end', name + '\n', 'head')
                    for m in models:
                        total += 1
                        if not known or m in known: t.insert('end', '  ' + m + '\n')
                        else: t.insert('end', '  %s  (new model, copied as-is)\n' % m, 'dim')
                    if not models: t.insert('end', '  no models\n', 'dim')
                    if other: t.insert('end', '  + %d other file(s)\n' % other, 'dim')
                if mods: t.insert('1.0', '%d mod(s), %d model file(s)\n' % (len(mods), total), 'dim')
            t.configure(state='disabled')

        def refresh_converted(self):
            name = self.v_name.get() or DEFAULT_NAME; man = read_manifest(name)
            self.cb_name.configure(values=converted_folders())
            self.tree.delete(*self.tree.get_children())
            self.report = read_report(name); self.sections = report_sections(self.report)
            if not man:
                self.l_out.configure(text='%s: nothing converted yet' % rel_show('Converted/' + name))
                self.models = {}
            else:
                self.models = man.get('models', {})
                for k, m in sorted(self.models.items()):
                    self.tree.insert('', 'end', iid='m:' + k, text=k, values=(m.get('mod', ''), m.get('built', ''), len(m.get('files', []))))
                pt = man.get('passthrough', {})
                if pt:
                    node = self.tree.insert('', 'end', iid='pt', text='Extra files copied as-is (%d)' % len(pt), values=('', '', len(pt)), open=False)
                    for rel, m in sorted(pt.items()):
                        self.tree.insert(node, 'end', iid='f:' + rel, text=rel, values=(m.get('mod', ''), '', ''))
                anims = man.get('anims', {})
                self.l_out.configure(text='%s\n%d model(s), %d extra file(s), %d material animation file(s)  -  manifest from %s'
                                     % (rel_show('Converted/' + name), len(self.models), len(pt), len(anims), man.get('tool', '')))
            label, files, info = lens_status(name)
            if label: self.l_lens.configure(text='Lens patch: %s  -  %s\n%s' % (rel_show('Converted/' + LENS_NAME), label, ', '.join('exefs/' + f for f in files)), style='Ok.TLabel')
            else: self.l_lens.configure(text='Lens patch: %s not written yet' % rel_show('Converted/' + LENS_NAME), style='Bad.TLabel')
            self.set_text(self.t_report, self.report or 'No report yet (it is written after each conversion).')
            self.show_detail()

        def show_detail(self):
            sel = self.tree.selection()
            if not sel:
                txt = 'Select a model to see what was converted.' if self.models else ''
                self.set_text(self.t_detail, txt); return
            out = []
            for iid in sel:
                if iid.startswith('m:'):
                    k = iid[2:]; m = self.models.get(k, {})
                    if k in self.sections: out.append(self.sections[k])
                    else:
                        out.append('== %s   (not in the last report: built %s)' % (k, m.get('built', '')))
                        for mat, l1 in sorted(m.get('l1', {}).items()): out.append('   L1 %-40s -> %s' % (mat, l1))
                    out.append('   files: ' + ', '.join(m.get('files', [])))
                    out.append('')
                elif iid.startswith('f:'): out.append('copied as-is: ' + iid[2:])
            self.set_text(self.t_detail, '\n'.join(out))

        # ---------------- pickers
        def pick_game(self):
            d = filedialog.askdirectory(title='Folder holding your game files (base + updates)', initialdir=self.v_game.get() or ROOT)
            if d: self.v_game.set(os.path.normpath(d))
        def pick_nup(self):
            f = filedialog.askopenfilename(title='Game .nup file', filetypes=[('NUP game file', '*.nup'), ('All files', '*.*')])
            if f: self.v_game.set(os.path.normpath(f))
        def pick_input(self):
            cur = clean_path(self.v_input.get())
            d = filedialog.askdirectory(title='Mod folder (or folder of mods) to convert',
                                        initialdir=os.path.dirname(cur) if cur else os.path.dirname(ROOT))
            if d: self.v_input.set(os.path.normpath(d))
        def open(self, p):
            if not open_path(p): messagebox.showinfo(GUI_VERSION, 'Not there yet:\n' + p)

        def check_packages(self):
            """the converter's packages must be importable by the Python the GUI runs it with"""
            def work():
                try: ok = subprocess.run([python_for_child(), '-c', 'import numpy, zstandard'], stdin=subprocess.DEVNULL,
                                         capture_output=True, **({'creationflags': 0x08000000} if os.name == 'nt' else {})).returncode == 0
                except OSError: ok = False
                if not ok: self.q.put(('line', '\033[91mThe converter packages (numpy, zstandard) are missing. Close this window and start the tool with '
                                       + ('BodiesOfTruth_GUI.bat' if os.name == 'nt' else 'bash BodiesOfTruth_GUI_linux.sh')
                                       + ': it sets them up by itself.\033[0m'))
            threading.Thread(target=work, daemon=True).start()

        def enable_drop(self):
            """drag-and-drop onto the window when tkinterdnd2 is installed (optional)"""
            try:
                from tkinterdnd2 import DND_FILES
                self.root.drop_target_register(DND_FILES)
                self.root.dnd_bind('<<Drop>>', lambda e: self.v_input.set(clean_path(self.root.tk.splitlist(e.data)[0])))
            except Exception: pass

        # ---------------- log
        def log(self, line, tag=None):
            t = self.t_log; t.configure(state='normal')
            if tag: t.insert('end', line + '\n', tag)
            else:
                parts, self.ansi = split_ansi(line, getattr(self, 'ansi', None))
                for txt, col in parts: t.insert('end', txt, col or ())
                t.insert('end', '\n')
            t.see('end'); t.configure(state='disabled')
        def clear_log(self): self.set_text(self.t_log, '')
        def copy_log(self):
            self.root.clipboard_clear(); self.root.clipboard_append(self.t_log.get('1.0', 'end'))

        # ---------------- running the converter
        def busy(self, on):
            self.b_go.configure(state='disabled' if on else 'normal')
            self.b_remove.configure(state='disabled' if on else 'normal')
            self.b_stop.configure(state='normal' if on else 'disabled')
            (self.pb.start if on else self.pb.stop)(*((12,) if on else ()))

        def common(self):
            g = clean_path(self.v_game.get())
            if not self.update_game_status():
                messagebox.showerror(GUI_VERSION, 'Pick your game files first (the folder holding base and updates, on update 131072, or a .nup file).')
                return None
            name = (self.v_name.get() or DEFAULT_NAME).strip()
            if name == LENS_NAME or any(c in name for c in '\\/:*?"<>|'):
                messagebox.showerror(GUI_VERSION, 'Choose a different model folder name.'); return None
            save_settings(game_files=os.path.abspath(g), gui_platform=self.v_platform.get(), gui_output_name=name)
            return g, name

        def convert(self):
            c = self.common()
            if not c: return
            g, name = c; inp = clean_path(self.v_input.get())
            if not os.path.isdir(inp):
                messagebox.showerror(GUI_VERSION, 'Choose the mod folder to convert.'); return
            if not find_romfs(inp):
                messagebox.showerror(GUI_VERSION, 'No romfs folder found in:\n' + inp); return
            save_settings(gui_last_input=inp)
            cmd = build_command('convert', g, self.v_platform.get(), name, inp=inp, dry_run=self.v_dry.get(),
                                keep_cloth=self.v_cloth.get(), no_patch=self.v_nopatch.get())
            self.run(cmd, 'convert')

        def remove_selected(self):
            keys = [i[2:] for i in self.tree.selection() if i.startswith('m:')]
            if not keys: messagebox.showinfo(GUI_VERSION, 'Select one or more models in the list first.'); return
            if not messagebox.askyesno(GUI_VERSION, 'Take these out of %s?\n\n%s' % (rel_show('Converted/' + self.v_name.get()), '\n'.join(keys))): return
            c = self.common()
            if not c: return
            g, name = c
            man = read_manifest(name) or {}
            plat = man.get('platform') or self.v_platform.get()      # keep the lens patch on the platform it was built for
            self.queue_cmds = [build_command('remove', g, plat, name, remove=k, no_patch=self.v_nopatch.get()) for k in keys]
            self.run(self.queue_cmds.pop(0), 'remove')

        def run(self, cmd, action):
            if self.proc: return
            self.action = action; self.nb.select(0)
            if action == 'convert': self.queue_cmds = []
            self.ansi = None; self.log('')
            self.log('> ' + ' '.join('"%s"' % a if ' ' in a else a for a in cmd[2:]), 'cmd')
            try: self.proc = start_process(cmd)
            except OSError as e:
                self.log('could not start Python: %s' % e, '91'); self.proc = None; return
            self.t0 = time.time(); self.busy(True)
            self.v_status.set({'convert': 'Converting...', 'remove': 'Removing...'}.get(action, 'Running...'))
            threading.Thread(target=self.reader, args=(self.proc,), daemon=True).start()

        def reader(self, proc):
            for line in proc.stdout: self.q.put(('line', line.rstrip('\r\n')))
            proc.wait(); self.q.put(('done', proc.returncode))

        def poll(self):
            try:
                for _ in range(400):
                    kind, val = self.q.get_nowait()
                    if kind == 'line':
                        if 'EOFError' in val: self.log(val + '   (the converter asked a question the GUI did not answer)', '91')
                        else: self.log(val)
                    else: self.finished(val)
            except queue.Empty: pass
            self.root.after(80, self.poll)

        def finished(self, code):
            self.proc = None; dt = time.time() - self.t0
            if code == 0 and getattr(self, 'queue_cmds', None):
                self.run_next(); return
            self.busy(False); self.refresh_converted()
            if code == 0:
                msg = {'convert': 'Dry run finished' if self.v_dry.get() else 'Conversion finished', 'remove': 'Removed'}.get(self.action, 'Done')
                self.v_status.set('%s in %.0fs' % (msg, dt)); self.log('-- %s (%.0fs)' % (msg.lower(), dt), '92')
                if self.action == 'convert' and not self.v_dry.get(): self.nb.select(1)
            elif code is not None and code < 0 or getattr(self, 'stopped', False):
                self.v_status.set('Stopped'); self.log('-- stopped', '91')
            else:
                self.v_status.set('Failed (exit code %s): see the output' % code); self.log('-- failed (exit code %s)' % code, '91')
            self.stopped = False; self.queue_cmds = []

        def run_next(self):
            cmd = self.queue_cmds.pop(0); action = self.action
            self.proc = None; self.busy(False); self.run(cmd, action)

        def stop(self):
            if self.proc and messagebox.askyesno(GUI_VERSION, 'Stop the converter now? Files it was writing may be left half done; convert again afterwards.'):
                self.stopped = True; self.queue_cmds = []
                try: self.proc.terminate()
                except OSError: pass

        def on_close(self):
            if self.proc:
                if not messagebox.askyesno(GUI_VERSION, 'The converter is still running. Stop it and close?'): return
                try: self.proc.terminate()
                except OSError: pass
            save_settings(gui_geometry=self.root.geometry())
            self.root.destroy()


def main():
    if not tk:
        sys.exit('Tkinter is missing. Windows: reinstall Python from python.org with "tcl/tk and IDLE" ticked. '
                 'Linux: install python3-tk (e.g. sudo apt install python3-tk). The command-line converter still works.')
    initial = clean_path(sys.argv[1]) if len(sys.argv) > 1 else None
    try:
        from tkinterdnd2 import TkinterDnD; root = TkinterDnD.Tk()
    except Exception: root = tk.Tk()
    if os.name == 'nt':
        try:
            import ctypes; ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception: pass
    App(root, initial if initial and os.path.isdir(initial) else None)
    root.mainloop()


if __name__ == '__main__':
    main()

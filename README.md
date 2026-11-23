# BodiesOfTruth-Conversion-Tool-OoTR
OoTRemake mod converter and lens patch for custom outfit switching effects

## LENS OUTFIT CONVERTER (BodiesOfTruth V1.3.3) Emulation/Recomp

Turns an NPC(NOT PLAYER) outfit mod into a SECOND OUTFIT that only appears through
the Lens of Truth.

| | |
| **Without the lens** | the NPC wears their normal outfit. |
| **Through the lens** | the NPC wears the modded outfit. |


## 0. GUI (NEW IN V1.3)

The same converter in a window. It works the same way on Windows and
Linux, and writes exactly what the command line writes (it runs
`BodiesOfTruth.py` for you).

**V1.3.1: one-click start.** Double-click `BodiesOfTruth_GUI.bat` (Windows) or
run `bash BodiesOfTruth_GUI_linux.sh` (Linux). The first start sets everything
up by itself (about a minute, internet needed); later starts open straight away.

**V1.3.3: big meshes fixed.** Vanilla pieces with more than 65,535 vertices (e.g. the
Great Fairy's leaf dress) were dropped from the lens-off outfit; they are now kept.


## 1. USAGE

1. Download and unzip the tool.

2. Start it: `BodiesOfTruth_GUI.bat` (Windows) or `bash BodiesOfTruth_GUI_linux.sh`
   (Linux) for the window, or `command-line\BodiesOfTruth.bat` /
   `command-line/BodiesOfTruth_linux.sh` for the command line. On first start the launcher:
   - finds Python 3.10 or newer. On Windows, if there is none, it offers to
     install Python 3.12 for you (or opens python.org);
   - installs the exact package versions the converter was built and tested
     with into the tool's own environment (`%LOCALAPPDATA%\BodiesOfTruth` on
     Windows, `~/.local/share/BodiesOfTruth` on Linux; delete it to remove).

   `command-line\install_requirements.bat` / `install_requirements_linux.sh` do the same
   setup on their own and can repair it. On Linux, if Python's `venv` or `tk`
   package is missing, run `bash command-line/install_requirements_linux.sh` once (it asks
   for your password to install them).

3. Select your
   game file folder. The game must be on update 131072. Selected
   folder is saved in `settings.json`. Delete `settings.json` to change
   the default folder.

4. Select which platform you play on:
   1. Emulation (Fritchii)
   2. Recomp (Hookshot/Longshot)
   3. Native (Official Hardware)

   This picks how the Lens of Truth code patch is added (see
   [PLATFORM PATCH METHODS](#platform-patch-methods) below). It asks every time you run the
   converter.

   The converter writes TWO mod folders:

   | Folder | Contents |
   |---|---|
   | `Converted\BodiesOfTruth - Custom` | the converted models, textures and packs (romfs) |
   | `Converted\LensPatch` | the Lens of Truth code patch for your platform (exefs) |

You can drag in:
- a single outfit mod (a folder that contains "romfs"), or
- a folder holding several outfit mods. They are all converted
  together.

Converting another mod later ADDS it to the same converted mod.
Converting the same NPC again replaces its earlier version.


## 2a. INSTALL (Emulation)

1. Copy BOTH folders, "BodiesOfTruth - Custom" and "LensPatch", into
   your game mod directory.

2. Enable mods through emulator settings. Compatible with default
   Fritchii code patches. May conflict if multiple mods make changes
   to the same character.


## 2b. INSTALL (Recompilation)

1. Copy BOTH folders, "BodiesOfTruth - Custom" and "LensPatch", into
   your game mod directory.

2. Place mod(s) at `<build version>\mods\<mod name>\` and rebuild once
   to install lens swap. Rebuilds for swapping converted mods is not
   necessary.


## PLATFORM PATCH METHODS

**Emulation (Fritchii)**<br>
Code module: the lens code ships as its own code file
(`exefs\subsdk1`), and the game's code only gets 10 small hooks that
jump into it.

**Recomp (Hookshot/Longshot) (Working on Longshot)**<br>
Code cave, recompiler-safe build (`app\patch\codecave_recomp`): the lens
code is patched into unused space at the end of the game's own code.

**Native (Official Hardware) (Unverified)**<br>
Code cave (`app\patch\codecave`).


## INTENDED TOOL BEHAVIOURS

**Two outfits, one NPC**<br>
The converter keeps the NPC's original outfit and adds the modded
outfit next to it. The game shows one or the other depending on the
Lens of Truth.

**Other NPCs stay untouched**<br>
Many NPCs share textures. The modded textures get their own names,
so only the converted NPC changes.

**Each outfit moves on its own**<br>
Physics such as jiggle bones added by the mod apply only to the lens
outfit. If the modded outfit removes something like cloth, its
bare skin no longer follows that cloth's physics.

**Physics files inside actor packs**<br>
If an input mod ships actor packs (for example jiggle-bone physics),
the converter gives every new or changed file inside them its own
size-table entry. Without these the game can hang after you pick
a save.

**Checked automatically**<br>
After building, the converter re-reads every model to make sure both
outfits are intact.

A short summary of each run is saved as `BodiesOfTruth_report.txt` in the
converted folder.


## EXTRA OPTIONS

Open a command prompt in this folder and type one of these. On Linux use
`bash command-line/BodiesOfTruth_linux.sh` in place of `command-line\BodiesOfTruth.bat`.

| Command | What it does |
|---|---|
| `command-line\BodiesOfTruth.bat "path\to\mod"` | Convert a mod (same as drag and drop). |
| `command-line\BodiesOfTruth.bat --list` | Show which NPCs are in the converted mod. |
| `command-line\BodiesOfTruth.bat --remove NAME` | Take one NPC back out. Example: `command-line\BodiesOfTruth.bat --remove Npc_Gerudo_GEN_001` |
| `command-line\BodiesOfTruth.bat "path\to\mod" --name "My Mod"` | Save the models to a different folder inside Converted (the lens patch still goes to `Converted\LensPatch`). |
| `command-line\BodiesOfTruth.bat "path\to\mod" --dry-run` | Preview what would happen, without writing anything. |
| `command-line\BodiesOfTruth.bat "path\to\mod" --keep-cloth-weights` | Let the lens outfit keep following the original cloth physics. |
| `command-line\BodiesOfTruth.bat "path\to\mod" --game-files "path\to\Game Files"` | Use a different game files folder (or a .nup file) this time. |
| `command-line\BodiesOfTruth.bat "path\to\mod" --platform emulation` | Skip the platform question (emulation, recomp or native). |


## GOOD TO KNOW

- **LIMITATION:** mods that affect the player character can not yet
  be converted.
  
- **Which mods work:** mods that replace an NPC's model file with a
  modified version of that same NPC. Mods may add bones, physics or
  textures, or remove clothing pieces.

- **Lens outfit colours:** some NPCs get colour variations from the game's
  animations. Inside the lens, the modded outfit shows its base colours.

- **Memory:** each converted NPC carries both outfits, so converting many
  NPCs in one area uses more memory.


## WHAT'S IN THIS FOLDER

| File / folder | |
|---|---|
| `BodiesOfTruth_GUI.bat` | **start here (Windows)** |
| `BodiesOfTruth_GUI_linux.sh` | **start here (Linux)** |
| `Converted\` | your converted mods (model folder + LensPatch) |
| `command-line\` | for advanced use: command-line launchers (`BodiesOfTruth.bat`, `BodiesOfTruth_linux.sh`) and setup repair (`install_requirements.bat`, `install_requirements_linux.sh`) |
| `app\` | the program itself (no need to open it) |
| `app\BodiesOfTruth.py` | the converter |
| `app\BodiesOfTruth_GUI.pyw` | the GUI |
| `app\requirements.txt` | package versions used by setup |
| `app\index\` | built-in list of every NPC model, so the converter doesn't need to scan the game |
| `app\lib\` | model, texture and file helpers, and the first-start setup |
| `app\patch\codemodule\` | Lens of Truth code patch, Emulation: subsdk1 + hooks (`src\` = build sources) |
| `app\patch\codecave\` | Lens of Truth code patch, Native: code cave IPS + pchtxt |
| `app\patch\codecave_recomp\` | Lens of Truth code patch, Recomp (Longshot): build 6, `src\` and `test\` |


## LICENSE AND CREDITS

BodiesOfTruth is free software under the GNU General Public License,
version 3 or later ([LICENSE.txt](LICENSE.txt)). Copyright (C) 2026 BodiesOfTruth
contributors. It comes with NO WARRANTY.

[CREDITS.txt](CREDITS.txt) lists the projects it uses or learned from (Python, NumPy,
zstandard, Tcl/Tk, LLVM, Unicorn, Keystone, Eglantine, BfresLibrary,
oead, Switch Toolbox, Blender and the emulators/recompilers it was
tested on).

Unofficial fan-made tool, not affiliated with or endorsed by Nintendo.
No game files are included; you need your own copy of the game.

# BodiesOfTruth-Conversion-Tool-OoTR
OoTRemake mod converter and lens patch for custom outfit switching effects

## LENS OUTFIT CONVERTER (BodiesOfTruth V1.3) Emulation/Recomp

Turns an NPC outfit mod into a SECOND OUTFIT that only appears through
the Lens of Truth.

| | |
|---|---|
| **Without the lens** | the NPC wears their normal outfit. |
| **Through the lens** | the NPC wears the modded outfit. |


## 0. GUI (NEW IN V1.3)

The same converter in a window. It works the same way on Windows and
Linux, and writes exactly what the command line writes (it runs
`BodiesOfTruth.py` for you).


## 1. USAGE

1. Install Python 3.10 or newer from python.org.
   During setup, tick "Add Python to PATH".

2. Run `install_requirements.bat` or `install_requirements_linux.sh`.
   It installs the exact package versions the converter was built and
   tested with (listed in `requirements.txt`).

3. Run `BodiesOfTruth.bat` or `BodiesOfTruth_linux.sh` and select your
   game file folder. The game must be on update 131072. Selected
   folder is saved in `settings.json`. Delete `settings.json` to choose
   a change the default folder.

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
Code cave, recompiler-safe build (`patch\codecave_recomp`): the lens
code is patched into unused space at the end of the game's own code.

**Native (Official Hardware) (Unverified)**<br>
Code cave (`patch\codecave`).


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

Open a command prompt in this folder and type one of these:

| Command | What it does |
|---|---|
| `python BodiesOfTruth.py "path\to\mod"` | Convert a mod (same as drag and drop). |
| `python BodiesOfTruth.py --list` | Show which NPCs are in the converted mod. |
| `python BodiesOfTruth.py --remove NAME` | Take one NPC back out. Example: `python BodiesOfTruth.py --remove Npc_Gerudo_GEN_001` |
| `python BodiesOfTruth.py "path\to\mod" --name "My Mod"` | Save the models to a different folder inside Converted (the lens patch still goes to `Converted\LensPatch`). |
| `python BodiesOfTruth.py "path\to\mod" --dry-run` | Preview what would happen, without writing anything. |
| `python BodiesOfTruth.py "path\to\mod" --keep-cloth-weights` | Let the lens outfit keep following the original cloth physics. |
| `python BodiesOfTruth.py "path\to\mod" --game-files "path\to\Game Files"` | Use a different game files folder (or a .nup file) this time. |
| `python BodiesOfTruth.py "path\to\mod" --platform emulation` | Skip the platform question (emulation, recomp or native). |


## GOOD TO KNOW

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
| `BodiesOfTruth_GUI.bat` | GUI launcher (Windows) |
| `BodiesOfTruth_GUI_linux.sh` | GUI launcher (Linux) |
| `BodiesOfTruth_GUI.pyw` | the GUI |
| `BodiesOfTruth.bat` | drag-and-drop launcher (Windows) |
| `BodiesOfTruth_linux.sh` | launcher (Linux) |
| `BodiesOfTruth.py` | the converter |
| `install_requirements.bat` | one-time setup (Windows) |
| `install_requirements_linux.sh` | one-time setup (Linux) |
| `requirements.txt` | package versions used by setup |
| `Converted\` | your converted mods (model folder + LensPatch) |
| `index\` | built-in list of every NPC model, so the converter doesn't need to scan the game |
| `lib\` | model, texture and file helpers |
| `patch\codemodule\` | Lens of Truth code patch, Emulation: subsdk1 + hooks (`src\` = build sources) |
| `patch\codecave\` | Lens of Truth code patch, Native: code cave IPS + pchtxt |
| `patch\codecave_recomp\` | Lens of Truth code patch, Recomp (Longshot): build 6, `src\` and `test\` |


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

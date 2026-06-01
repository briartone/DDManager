# Build Instructions

This repository contains the full source for `DD Manager`.

## Source Entry Point

- Main application: `dd2.py`
- Helper modules: `categories.py`, `localization.py`, `paths.py`, `state.py`, `legacy_loadout.py`
- Build script: `build.ps1`
- PyInstaller runtime hook: `pyi_rth_tk_paths.py`

## Build Environment

- Windows
- Python 3.14
- PyInstaller installed into that Python environment

## Clean Build Steps

1. Open PowerShell in the repository root.
2. Ensure Python is available on `PATH`.
3. Install PyInstaller:

```powershell
python -m pip install pyinstaller
```

4. Run the project build script:

```powershell
.\build.ps1
```

## What The Build Script Does

`build.ps1` performs the release build by:

- building `dd2.py` with PyInstaller in `--windowed --onedir` mode
- bundling the required Tkinter/Tcl/Tk runtime files
- copying the built app into `release\DD Manager Portable`
- creating `release\DD Manager Portable <version>.zip`

The primary packaged executable is created under:

- `dist\DD Manager\DD Manager.exe`

The portable release archive is created under:

- `release\DD Manager Portable <version>.zip`

## Notes For Review

- The program is a local Tkinter desktop app written in Python.
- It does not include a custom installer.
- It is packaged with PyInstaller, which can sometimes trigger antivirus heuristics.
- UPX compression is disabled in the current build configuration to reduce false positives on some scanners.

## Current Packaging Choice

The current build path disables UPX in both the PyInstaller command line and the checked-in spec file. To rebuild with the same lower-false-positive packaging profile, run:

```powershell
.\build.ps1
```

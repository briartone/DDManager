# Darkest Dungeon Mod Manager

Small Windows Tkinter tool for sorting Darkest Dungeon mods and writing the enabled mod list into `persist.game.json`.

Auto-detect works best on Steam installs. Some non-Steam installs, including GOG setups, may still need manual path selection through `File Paths`.

## Repository Status

This repository is not open source.

Code is published here for visibility and release distribution, but all rights
are reserved. You may not copy, modify, redistribute, or reuse this project
without prior written permission.

See [`LICENSE.md`](LICENSE.md) for the repository terms.

## Quick Start

1. Run `dd2.py`.
2. Click `Auto Detect`.
3. If Auto Detect finds your mods, click `Refresh Mods` if you want to rescan for new installs, updates, or subscriptions, then review the enabled/disabled lists.
4. Choose a profile from the `Profile` menu.
5. Click `Load Profile Mods` to mirror that profile's current active mod list and order in the manager.
6. Click `Patch Selected Profile` to update that profile's `persist.game.json`.
7. Launch Darkest Dungeon.

If Auto Detect misses part of your setup, open `File Paths`, confirm or fill in the detected folders, save them, then click `Refresh Mods`.

## Save Patching

`Patch Selected Profile` is the main workflow and should cover normal use.

`Patch Chosen Save` lets you manually pick a `persist.game.json`.

`Patch Auto-Detected Save (Legacy)` is still available from the `Tools` menu as a fallback if profile detection is not the right fit for a specific case.

Patch actions:

- create a timestamped backup beside the original save
- validate the patched save metadata
- write the patched data back to the default `persist.game.json` filename

That means the game can load the patched save without manually renaming or moving files.

## Restore

Use `Restore Last Backup` if you want to undo the most recent patch. The backup file remains beside the save file.

## Troubleshooting

Click `Check Setup` to see:

- whether the mods folder is valid
- how many mods are loaded and enabled
- which profile is selected
- whether a save file was detected
- whether the save contains the expected `applied_ugcs_1_0` mod block
- the most recent backup path

If setup detection fails, use `File Paths` to set the folders manually and `Patch Chosen Save` if you need to point at a save file directly.

If setup detection fails or a non-Steam install is only partially detected:

1. Click `File Paths`.
2. Check the populated live paths for the game install folder, active mods folder, local mods folder, Workshop mods folder, and profile save file.
3. Use `Auto` to fill any missing field from the current detector result.
4. Use the `Browse` buttons inside `File Paths` to manually select any folder or save file Auto Detect could not find.
5. Click `Save File Paths`.
6. Click `Refresh Mods`.
7. Re-open the profile menu or use `Refresh` beside the profile picker if needed.

Non-Steam note:

- Steam installs are the primary auto-detect target.
- GOG and other non-Steam installs may need `File Paths` even when saves are found correctly.
- Linux non-Steam saves are now checked under `~/.local/share/Red Hook Studios/Darkest/`, but manual path overrides are still the safest fallback when a layout is unusual.

## Notes

- The app remembers your working mod state automatically, so the older loadout import/export buttons are currently disabled in the UI.
- Legacy patch helpers are still available under `Tools` if you need them later.

## Releases

`.\build.ps1` now does two things:

1. Builds the Windows app into `dist/DD Manager/`
2. Creates a portable release zip at `release/DD Manager Portable.zip`

To publish a GitHub Release automatically:

See [`CHANGELOG.md`](CHANGELOG.md) for patch and release notes.

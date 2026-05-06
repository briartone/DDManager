# Darkest Dungeon Mod Manager

Small Windows Tkinter tool for sorting Darkest Dungeon mods and writing the enabled mod list into `persist.game.json`.

## Quick Start

1. Run `dd2.py`.
2. Click `Auto Detect`.
3. If Auto Detect finds your mods, review the enabled/disabled lists.
4. Choose a profile from the `Profile` menu.
5. Click `Load Profile Mods` to mirror that profile's current active mod list and order in the manager.
6. Click `Patch Selected Profile` to update that profile's `persist.game.json`.
7. Launch Darkest Dungeon.

If Auto Detect cannot find your mods, click `Browse`, select the folder that contains your mod folders, then click `Load Mods`.

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

If setup detection fails, use `Browse` for the mods folder and `Patch Chosen Save` for the save file.

## Notes

- The app remembers your working mod state automatically, so the older loadout import/export buttons are currently disabled in the UI.
- Legacy patch helpers are still available under `Tools` if you need them later.

## Releases

`.\build.ps1` now does two things:

1. Builds the Windows app into `dist/DD Manager/`
2. Creates a portable release zip at `release/DD Manager Portable.zip`

To publish a GitHub Release automatically:

```powershell
git add .
git commit -m "Prepare v0.1.0"
git push
git tag v0.1.0
git push origin v0.1.0
```

This repo includes a GitHub Actions workflow at `.github/workflows/release.yml` that builds the portable zip on tag pushes matching `v*` and uploads:

- `DD Manager Portable.zip`
- `DD Manager Portable.sha256`

If you want to draft release notes first, create the tag after your final code push, then edit the generated GitHub Release page.

See [`CHANGELOG.md`](CHANGELOG.md) for patch and release notes.

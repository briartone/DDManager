# Changelog

All notable changes to this project should be listed here.

## v0.1.4 - 2026-05-11

- Improved Windows profile auto-detection by reading Steam install paths from the registry instead of relying only on default `Program Files` locations.
- Added a Windows fallback scan for `Documents\\Darkest` profile saves so profiles can still be found when Steam Cloud paths are missing or not in use.

## v0.1.3 - 2026-05-10

- Added preliminary Linux-aware Steam detection for common install roots and library paths while keeping the current Windows auto-detect behavior unchanged.
- Added a Linux fallback for launching Darkest Dungeon through Steam when `os.startfile(...)` is not available.
- Added Linux font fallbacks for the main UI, splash screen, and code preview while preserving the existing Windows font choices.

## v0.1.2 - 2026-05-09

- Fixed Shift-click multi-select in both mod panels so repeated range selections keep expanding the current highlight instead of collapsing it or jumping to an unexpected anchor.
- Kept selection-anchor tracking stable across drag, reorder, and cross-panel moves so follow-up Shift selections behave consistently after list interactions.

## v0.1.1 - 2026-05-08

- Added an explicit proprietary `LICENSE.md` and README notice clarifying that the repository is not open source.
- Simplified the main UI around a profile-first patching flow.
- Removed `Patch Auto-Detected Save` from the main action row and kept it as `Tools > Patch Auto-Detected Save (Legacy)`.
- Disabled the `Save Loadout` and `Load Loadout` buttons in the UI while preserving the underlying functionality in code for possible future reuse.
- Updated the build script to retry portable zip creation so Windows file locks are less likely to break release packaging.
- Profile picker now shows save date and hours played from save metadata when available.
- Rapid repeated view-mode clicks are debounced, and icon loading after a view switch is backgrounded to prevent freezing.

## v0.1.0 - 2026-05-06

- First tagged GitHub release.
- Added GitHub Actions release automation for version tags matching `v*`.
- Added portable release packaging through `build.ps1`.
- Published `DD Manager Portable.zip` and a matching SHA256 file through GitHub Releases.

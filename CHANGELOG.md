# Changelog

All notable changes to this project should be listed here.

## Unreleased

- Simplified the main UI around a profile-first patching flow.
- Removed `Patch Auto-Detected Save` from the main action row and kept it as `Tools > Patch Auto-Detected Save (Legacy)`.
- Disabled the `Save Loadout` and `Load Loadout` buttons in the UI while preserving the underlying functionality in code for possible future reuse.
- Updated the build script to retry portable zip creation so Windows file locks are less likely to break release packaging.

## v0.1.0 - 2026-05-06

- First tagged GitHub release.
- Added GitHub Actions release automation for version tags matching `v*`.
- Added portable release packaging through `build.ps1`.
- Published `DD Manager Portable.zip` and a matching SHA256 file through GitHub Releases.

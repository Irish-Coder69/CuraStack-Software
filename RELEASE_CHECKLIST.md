# CuraStack Software Release Checklist

## Pre-Release
- Confirm `version.json` is updated (major/minor/patch/build).
- Ensure Help menu update flow points to GitHub `releases/latest`.
- Verify no local debug changes are left in source.
- Use Python 3.11/3.12 build environment (`.venv311` preferred).
- Confirm GitHub CLI is installed and authenticated (`gh auth status`) before running automated release publish.
- If `gh` is missing, install it: `winget install --id GitHub.cli --accept-package-agreements --accept-source-agreements`

## Build
- Run `./build_installer.ps1` from repo root.
- Confirm output line: `Installer created at: L:\CuraStack Software\release\CuraStack Software-Installer.exe`.
- Smoke test installer on local machine (install + launch).
- Smoke test app startup and Help > Check for Updates.

## Commit and Push
- Commit source/version changes.
- Do NOT commit `release/CuraStack Software-Installer.exe` (upload it only in GitHub Release).
- Push to `main`.

## Publish GitHub Release
- Create tag: `v<major>.<minor>.<patch>-build<build>`.
- Upload `release/CuraStack Software-Installer.exe` as release asset.
- Ensure release is marked `Latest` (not draft/prerelease).

## Post-Release Validation
- Run updater check from one older installed build.
- Confirm download + install completes and app relaunches.
- Confirm user data persists (`theratrak.db` remains intact).
- Verify startup log exists at app root (`startup.log`) for diagnostics.

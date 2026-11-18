# Maintainer notes

## Releasing

Run **tools\release.bat** on a clean `main`. It asks for the new version, runs the tests and opens Notepad for the release notes: write what changed, save and close Notepad. It then sets `APP_VERSION` in `src/app_identity.py`, commits, tags `vX.Y.Z` and pushes.

The workflow in `.github/workflows/build-executables.yml` then builds and tests Windows, Linux and the signed Android APK, and publishes all three under Releases with the notes from `docs/release-notes/<version>.md`. Versions starting with `0.` are marked as pre-releases. If any build fails, nothing is published; fix it and run the workflow again from the Actions tab, or delete the tag and release again.

## Android signing secrets

Phones only accept an update signed with the same key as the installed app, so GitHub uses the release key from WSL (`~/.config/album-drive`). Add these repository secrets once (GitHub > Settings > Secrets and variables > Actions):

- `ANDROID_KEYSTORE_BASE64`: in PowerShell, `wsl -- bash -c "base64 -w0 ~/.config/album-drive/release.keystore" | Set-Clipboard`
- `ANDROID_KEY_PASSWORD`: in PowerShell, `wsl -- bash -c "cat ~/.config/album-drive/release-key-password.txt" | Set-Clipboard`

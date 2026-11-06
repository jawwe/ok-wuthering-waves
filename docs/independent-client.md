# AsterDesk independent client

Maintained on `codex/independent-client` in
[`jawwe/ok-wuthering-waves`](https://github.com/jawwe/ok-wuthering-waves/tree/codex/independent-client).
The existing automation and pinned libraries use a separate application identity,
configuration directory, workshop snapshots and release channel.

## Portable use

Extract the complete folder and run `AsterDesk.exe`. Its child GUI process is
`AsterRuntime.exe`. The app title, launcher metadata, icon and log filenames use
the new identity. Internal modules, third-party metadata, source and license
notices remain intact. This removes visible branding; it is not binary obfuscation.
The package includes Python and the complete current workshop snapshot.
User data lives in `data/` and is never included in a build.

The Character Code page supports editing, import/export and workshop browsing.
Client Settings provides the keyboard/mouse switch, independent release download
and one-time old configuration import. Import validates and stages the selected
files, then applies them before the next startup. Existing settings are backed up
to `data/config-before-import`. The original installation is never modified.

## Workshop cache and history

The primary site is `https://okwwcharcode.ok-script.com`. GitHub Raw for
`ok-oldking/ok-ww-char-code` is the secondary index/download source; the CF domain
is a final catalog fallback. Working old URLs are not rewritten to the CF domain.

The workshop immediately displays the latest valid local/bundled catalog, then
refreshes the index and all packages in the background. Successful ZIPs are checked
for shape, Python syntax and stored with SHA-256 identities. Caching never executes
a script. Timeouts, TLS/HTTP errors and invalid responses retain the last usable
cache. The UI displays its timestamp and any packages that failed to refresh.
Explicit team import retains the normal preview, confirmation and character checks.

`resources/workshop/current.json` selects the bundled snapshot. Captured indexes
stay in `snapshots/`, with immutable ZIPs in `archives/`. Earlier published versions
and captured historical catalogs are retained. Do not delete referenced archives.

```powershell
.\.venv\Scripts\python.exe tools/snapshot_workshop.py
.\.venv\Scripts\python.exe tools/snapshot_workshop.py --ref <upstream-commit> --historical
```

Commit new snapshots/archives on this branch before releasing. The packaged app
can browse and import every bundled configuration on its first offline start.
Subsequent network cache data is stored under `data/cache/workshop`.

## Input modes

The persisted switch controls all framework keyboard and mouse operations:
background window messages or system input. Background is the default. Stop a
running task first; changes apply between tasks. System mode focuses the game.
Inputs are not sent to unrelated foreground windows. Owned keys and buttons are
released even after focus is lost. Existing activity-specific foreground gestures
continue to use system input when needed.

## Build and updates

```powershell
.\.venv\Scripts\python.exe tools/build_portable.py --version 1.0.0
```

Use Windows x64 Python 3.12 and the pinned `requirements.txt`. The builder refreshes
and verifies the snapshot. `--offline-snapshot` explicitly reuses the checked-in
snapshot. Outputs: `dist/AsterDesk-<version>-windows-x64.zip` and SHA-256 file.
No original updater repository, signing account, installer or build action is used.

The independent workflow accepts this branch and `aster-vX.Y.Z` tags. Original
`vX.Y.Z` releases are ignored. Client Settings checks only this repository and
accepts matching portable ZIPs plus checksums. Close the client before extracting
a downloaded update, and preserve `data/`. Missing independent releases never
fall back to an original release.

Upstream attribution is preserved through Git history and the AGPLv3 license.

# OneBoard customer releases

Customer update checks are disabled by default. No production endpoint exists in
this repository. The customer UI never invokes `update.bat`, Git, pip, or the
upstream repository. `update.bat` remains a source-checkout developer tool and is
excluded from customer packages.

The inherited batch file runs plain `git pull`, which follows the current
branch's configured tracking branch; it does not select the Git remote named
`upstream`. A deliberate upstream sync starts with an explicit
`git fetch upstream` and a reviewed integration into `oneboard-dev`.

Developer flow: review upstream changes, deliberately merge them into
`oneboard-dev`, validate, build a OneBoard release, then publish through infrastructure
owned by the distributor. Do not publish OneBoard features to `main` or `upstream/main`.

`version.py` centralizes the application version, numeric Windows file version,
default channel, and empty manifest/release URLs. A distributor may configure the
normal application settings with `oneboard_update_enabled: true`,
`oneboard_update_manifest_url` (HTTPS), and `oneboard_update_channel` (default
`stable`). Optional `oneboard_release_url` is a fallback release page. Enabling
checks without a manifest URL performs no request. There are no background checks.

The HTTPS manifest is a small JSON object with `version`, `channel`, and
`release_url` fields. Versions use `major.minor.patch` optionally followed by
`-alphaN`, `-betaN`, or `-rcN`. The application checks only when the user clicks
Check for updates in Advanced / Version and updates. A newer verified manifest
enables an explicit Open OneBoard release page action. Users install the new package
using its normal installer/extraction flow; settings remain in their data directory.

The configured HTTPS service is a trust boundary. Manifests are size-limited and
validated; redirects, insecure URLs, and channel mismatches are rejected. This is
release discovery, not an authenticated executable updater: there is no manifest
signature scheme, binary download, execution, automatic installation, or rollback.
Production release signing, hosting, and recovery policy remain deployment work.

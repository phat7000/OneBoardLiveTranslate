# OneBoard Windows packaging

The customer ZIP contains `OneBoardLiveTranslate.exe`, ordinary application
modules under `app`, and a complete isolated Python runtime under `runtime`.
It needs no Git checkout, separately installed Python, pip commands, or batch-file
launcher. The builder retains upstream dynamic imports and multiprocessing; it
does not use a one-file freezer. `build_release.ps1` remains an upstream developer
reference and must not be used for customer OneBoard releases.
The copier omits Python caches, installed package test/fixture trees (including
PyCryptodome `SelfTest`), the unreferenced `transformers/testing_utils.py` test
helper, and the known pytest/iniconfig/pluggy development stack while preserving
runtime package metadata and license/notice files. License subtrees remain intact
even when a vendor places a notice below a directory named `test`. A post-smoke
hygiene gate stops packaging if excluded Python artifacts reappear or an
inventoried dependency notice is missing.

## Build from a clean developer checkout

Use Windows x64, Python 3.12 x64, and the Windows .NET Framework 4 C# compiler
already supplied on supported Windows installations. The commands below are
developer build steps; the customer never runs them. Do not install system-wide
tools as part of the builder. Before running them, assign a new approved
`VERSION` and `WINDOWS_VERSION` in `version.py` and commit that change.

```powershell
git switch oneboard-dev
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -r requirements.txt "yasbd-lib>=0.15,<1.0" pytest
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest .\tests
git diff --check
git status --short
$ReleaseVersion = & .\.venv\Scripts\python.exe -B -c "from version import VERSION; print(VERSION)"
powershell -NoProfile -ExecutionPolicy Bypass -File .\build_oneboard_release.ps1 -Version $ReleaseVersion
Get-FileHash ".\release\OneBoardLiveTranslate-$ReleaseVersion-win-x64.zip" -Algorithm SHA256
```

The status command must be empty before a release build. The manual GitHub
workflow uses the same OneBoard builder and only uploads a workflow-run artifact;
it does not publish a GitHub release or react automatically to tags.

Set product identity in `branding.py` and the approved release version in
`version.py` before committing. Version `0.2.0-rc1` is revoked; the builder
blocks recreating its ZIP or installer. Builds require a clean worktree by
default.
`-AllowDirty` is for development QA; its manifest explicitly records
`dirty_preview: true`. `-SkipArchive` runs all build and runtime checks but leaves
only the application directory. The output ZIP is
`release/OneBoardLiveTranslate-<VERSION>-win-x64.zip`; the staging directory is
`release/OneBoardLiveTranslate`. Existing unrelated release files are preserved.

The base build above is a **CPU distribution**; it does not promise GPU support
just because the customer's computer has a GPU. Prepare and validate a separate
environment with the appropriate supported PyTorch/CTranslate2 GPU libraries when
publishing a GPU distribution. Do not infer a production hardware target from the
development machine. Exact bundled package versions are recorded in each
artifact's `runtime-requirements.txt` and `dependency-inventory.json`; upstream
requirements remain open ranges, so a clean future resolution is not guaranteed
to reproduce an earlier build byte for byte.

## Installer and icon

`packaging/OneBoardLiveTranslate.iss` supports **Inno Setup 6.3 or later**, per-user
installation without elevation, a Start Menu shortcut, an optional Desktop
shortcut, version resources, and uninstall support. The compiler is an optional
developer dependency; the builder never downloads or installs it. With a compiler
already available (including a manually prepared local tool directory):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\build_oneboard_release.ps1 -Iscc 'C:\Tools\InnoSetup\ISCC.exe'
```

This adds `release/OneBoardLiveTranslate-Setup-<VERSION>.exe`. A production
OneBoard `.ico` asset can be supplied via `-Icon 'C:\Assets\OneBoard.ico'`; the
same icon is applied to launcher and installer. Until an approved icon exists,
the executable uses the compiler's default icon. Signing is a release-publisher
step and is not simulated by this build. A package without signing is unsigned.

## User data and verification

The distribution marker selects `%LOCALAPPDATA%\OneBoardLiveTranslate` for
settings, models, transcripts and logs. Updates and uninstalls do not delete that
directory. Source checkouts keep the inherited repository-local layout. For a
separate portable profile, set an **absolute** `ONEBOARD_DATA_DIR` before launch.
Neither the ZIP nor installer contains personal settings, downloaded ASR/LLM
weights, the developer virtual environment, Git metadata, or upstream updater.
The small Silero VAD asset is part of its required dependency wheel.

Every build runs the actual GUI EXE with a fresh data directory and a PATH without
developer tools, using an unrelated working directory and invalid external
`PYTHONHOME`/`PYTHONPATH`. Offline smoke checks cover application/native library
imports, Qt icon rendering, bundled Silero VAD, and a spawned worker using the
bundled interpreter. The report is `release/packaging-smoke.json`. This does not
substitute for live microphone/loopback testing, real ASR/translation models,
clean-machine installation, GPU testing, or installer uninstall QA.

Manual relocation test after extraction:

```powershell
Start-Process -FilePath 'C:\Extracted\OneBoardLiveTranslate\OneBoardLiveTranslate.exe' -WindowStyle Hidden -Wait
```

Verify first-run setup, model download consent, language presets, Start/Stop,
Advanced settings, restart persistence, and uninstall on a separate Windows user
profile/VM before publishing. Ollama remains a separately managed prerequisite.

The builder requires and ships the OneBoard GPL-3.0-only text as `LICENSE`, the
preserved upstream LiveTranslate MIT attribution as
`LICENSES/LiveTranslate-MIT.txt`, the verified vendored FunASR MIT attribution as
`LICENSES/FunASR-MIT.txt`, and `THIRD_PARTY_NOTICES.md`. A build fails if any of
these project-level notice files is missing. It also preserves all copied wheel
license/notice files and CPython `runtime/LICENSE.txt`. The portable ZIP contains
the complete verified stage, and the installer recursively installs the same
files while displaying `LICENSE` in its license step. Metadata is a licensing
inventory, not legal clearance. Review all runtime components and separately
downloaded model weights before distribution.

## Release-source mapping

Every published binary release must map to one exact Git tag. For version
`1.0.0`, tag `v1.0.0` must identify the precise clean source commit used to build
the matching portable ZIP and installer. Publish that tag, the matching binaries,
and the matching license and notice files as one release set. Record the same
commit in `distribution.json`; never publish an `-AllowDirty` QA build as a
release. If a binary changes, create a new version and tag rather than replacing
an artifact under an existing tag.

See `RELEASE_LICENSING_REVIEW.md` for the remaining third-party, native-library,
codec, and model-license release gates before publishing a generated candidate.

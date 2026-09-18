# OneBoard Windows packaging

The customer ZIP contains `OneBoardLiveTranslate.exe`, ordinary application
modules under `app`, and a complete isolated Python runtime under `runtime`.
It needs no Git checkout, separately installed Python, pip commands, or batch-file
launcher. The builder retains upstream dynamic imports and multiprocessing; it
does not use a one-file freezer. `build_release.ps1` remains an upstream developer
reference and must not be used for customer OneBoard releases.
The copier omits Python caches, installed package test/fixture trees (including
PyCryptodome `SelfTest`), the unreferenced `transformers/testing_utils.py` test
helper, and the pytest/iniconfig/pluggy development stack while preserving
runtime package metadata and license/notice files. The RC3 pruning pass also
removes pip/ensurepip, CPython debug/test/Tk helpers, ONNX sample datasets,
native build headers/link libraries, PyAV/FFmpeg, cuDNN/CUDA runtime DLLs and
unused Qt modules/plugins. License subtrees remain intact even when a vendor
places a notice below a directory named `test`.

The builder applies a hash-gated lazy PyAV import to staged faster-whisper
`1.2.1`; OneBoard's supported capture path supplies decoded NumPy arrays. It
does not modify the developer environment. Exact Qt binding/DLL/plugin
allowlists and forbidden runtime patterns fail closed, as do unreviewed native
version/hash changes and any staged Python distribution without an auditable
license file.

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
`version.py` before committing. Versions `0.2.0-rc1` and `0.2.0-rc2` are
protected historical candidates; the builder blocks recreating either ZIP or
installer. Builds require a clean worktree by default.
`-AllowDirty` is for development QA; its manifest explicitly records
`dirty_preview: true`. `-SkipArchive` runs all build and runtime checks but leaves
only the application directory. The output ZIP is
`release/OneBoardLiveTranslate-<VERSION>-win-x64.zip`; the staging directory is
`release/OneBoardLiveTranslate`. Existing unrelated release files are preserved.

The base build above is a **CPU distribution**. It contains CPU PyTorch and no
CUDA, cuDNN, PyAV, FFmpeg or Qt Multimedia runtime. CTranslate2's required
upstream DLL is monolithic and contains dormant dynamically loaded CUDA code,
but no GPU runtime is bundled or supported by this package. Prepare, document
and validate a separate environment for any future GPU distribution. Exact
bundled package versions are recorded in `runtime-requirements.txt` and
`dependency-inventory.json`; significant native binaries are recorded in
`native-component-inventory.json`, and reviewed exclusions in
`runtime-exclusions.json`.

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

Every build runs the actual GUI EXE with a fresh data directory and a PATH
without developer tools, using an unrelated working directory and invalid
external `PYTHONHOME`/`PYTHONPATH`. Offline smoke checks cover application/native
imports, explicit PyAV/QtMultimedia absence, Qt rendering, the primary window,
Display Window, Advanced Control Panel, bundled Silero VAD, CTranslate2 CPU
compute types and a spawned worker using the bundled interpreter. The report is
`release/packaging-smoke.json`. This does not substitute for live
microphone/loopback testing, real translation service QA, every optional model,
clean-machine installation, GPU testing, or installer uninstall QA.

Manual relocation test after extraction:

```powershell
Start-Process -FilePath 'C:\Extracted\OneBoardLiveTranslate\OneBoardLiveTranslate.exe' -WindowStyle Hidden -Wait
```

Verify first-run setup, model download consent, language presets, Start/Stop,
Advanced settings, restart persistence, and uninstall on a separate Windows user
profile/VM before publishing. Ollama remains a separately managed prerequisite.

The builder requires and ships the OneBoard GPL-3.0-only text, preserved
LiveTranslate and FunASR MIT notices, exact supplemental records for the RC2
missing-license set, QtBase 6.11.2 notices, and the CTranslate2/oneDNN/Intel
OpenMP license set. It preserves every copied wheel notice and CPython
`runtime/LICENSE.txt`. A missing source notice, missing inventoried dependency
license or native notice stops the build. The portable ZIP contains the complete
verified stage, and the installer recursively installs that same stage while
displaying `LICENSE`. Metadata is an audit record, not universal legal
clearance; see `RELEASE_LICENSING_REVIEW.md`.

## Release-source mapping

Every published binary release must map to one exact Git tag. For version
`1.0.0`, tag `v1.0.0` must identify the precise clean source commit used to build
the matching portable ZIP and installer. Publish that tag, the matching binaries,
and the matching license and notice files as one release set. Record the same
commit in `distribution.json`; never publish an `-AllowDirty` QA build as a
release. If a binary changes, create a new version and tag rather than replacing
an artifact under an existing tag.

See `RC3_RUNTIME_AUDIT.md` for reachability decisions and
`RELEASE_LICENSING_REVIEW.md` for remaining public-release review items.

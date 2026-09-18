# OneBoard Live Translate MVP release readiness

> Historical RC1 record. For the current RC3 decision, use
> `RELEASE_LICENSING_REVIEW.md` and `RC3_RUNTIME_AUDIT.md`.

Audit date: 2026-09-10

Project-license decision updated: 2026-09-11

GPL release validation updated: 2026-09-13

Public-source audit validation updated: 2026-09-14

Historical candidate: `0.2.0-rc1` (`0.2.0.0` Windows file version), revoked
Target: Windows x64, CPU base distribution

No replacement candidate was built during the public-source audit. The revoked
RC1 archive was removed from this checkout; any retained copy predates the
credential/provenance cleanup and must not be published. A fresh, unarchived
`dirty_preview` stage was created only for the required packaging smoke.

## Release decision

**HOLD for customer publication.** The Phase 2 product implementation, automated
tests, and portable packaging path are complete within this workstation, but the
candidate is not approved for customers. The manual Windows/audio/model matrix
remains open, no installer compiler is available on this machine, and the
artifact-level native-library, codec, and model licensing review remains open.
Vendored FunASR Python-source provenance is verified. See
[RELEASE_LICENSING_REVIEW.md](RELEASE_LICENSING_REVIEW.md)
and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for the evidence, dependency
inventory, and model review boundaries.

The final project-license decision is free and open-source distribution under
`GPL-3.0-only` with PyQt6 retained. The chosen strategy does not require a
PySide6 migration or commercial PyQt license; this does not clear the remaining
artifact-specific reviews.

The final clean ZIP is intentionally generated after the commit containing this
report so `distribution.json` can record that immutable source revision. Its
SHA-256 and final smoke report are build outputs outside Git and belong in the
release handoff record; the commands below verify them. Any dirty-preview stage is
QA evidence only and must not be published.

## Phase status and commits

| Phase | Status | Commit | Result |
| --- | --- | --- | --- |
| 2.3 Product UX | Complete; manual RC exercise pending | `392f02076047fb4133b6d914fb8a1874f43351e9` | OneBoard product window, explicit EN/VI presets, bounded two-pane transcript, Start/Stop, Clear, and Advanced access. |
| 2.4 Runtime readiness | Complete; machine is not externally ready | `dbdf99b49dac79704399458d4769379f9f0293f1` | Audio, ASR runtime/model, Ollama service/model, and CPU/GPU readiness checks with explicit download actions. |
| 2.5 First-run setup | Complete; manual clean-profile exercise pending | `18c6a7c7755ce7f97012e3f86a2ba85e7e00138f` | Reopenable setup wizard and persisted completion state. |
| 2.6 Windows packaging | Portable complete; installer partial | `d9c453e5fe70afeb577be04655861df1807390a3` | Portable runtime builder, launcher, smoke test, and Inno Setup definition exist. Installer build is blocked on this machine by missing ISCC. |
| 2.7 Update architecture | Complete; intentionally disabled | `87f770ef83bfaedbea0a1ea8b0016c2cdec6db71` | Configurable HTTPS OneBoard manifest discovery; no upstream pull, download, or execution path in the customer UI. |
| 2.8 QA, licensing, hardening | Partial / release hold | This commit | Automated and repository audits are complete and the project license is finalized as `GPL-3.0-only`. Manual end-to-end QA, final packaging, signing, and third-party/model licensing review remain open. |

The product branding foundation is commit
`5c1f065fa9a1d5b71113ce6d2b1a3814b7421d0f`.

## Product modules and release files

Phase 2.3 added `oneboard_app.py`, `oneboard_presets.py`,
`oneboard_transcript_view.py`, `oneboard_ui.py`, and focused UI/controller tests.
Phase 2.4 added `oneboard_readiness.py`; Phase 2.5 added
`oneboard_setup.py`. Phase 2.6 added `oneboard_launch.py`,
`oneboard_paths.py`, `version.py`, `build_oneboard_release.ps1`,
`packaging/build_oneboard.py`, `packaging/OneBoardLauncher.cs`,
`packaging/OneBoardLiveTranslate.iss`, `PACKAGING.md`, and packaging tests.
Phase 2.7 added `oneboard_updates.py`, `ONEBOARD_UPDATES.md`, and update tests.
Phase 2.8 adds this report, the third-party notices/inventory, regression coverage
for safe checked-in defaults, and focused fixes found by the audit.

The changes to upstream-owned files are deliberately small:

- `main.py` keeps the inherited orchestration as `upstream_main()` and routes the
  normal entry point to `oneboard_app.run()`. It also redirects logs and transcript
  output through `oneboard_paths.data_dir()`. A standalone widget could not replace
  startup behavior or move mutable installed data safely.
- `control_panel.py` keeps the full upstream panel and moves settings/transcript
  paths through `oneboard_paths.data_dir()` so upgrades and uninstall do not remove
  user state.
- `model_manager.py` moves the model cache through the same path adapter. Model
  management behavior is unchanged.
- `dialogs.py`, `subtitle_overlay.py`, `subtitle_window.py`, and localized display
  strings use centralized values from `branding.py`; internal logger namespaces and
  upstream attribution remain intact.
- `config.yaml` supplies safe OneBoard EN-to-VI, Whisper Small CPU, and local Ollama
  fallbacks. Advanced still exposes the inherited engines, languages, devices, and
  model settings.

No ASR, VAD, capture, translation, worker, or model-download algorithm was
rewritten for the OneBoard layer. The detailed integration rationale is preserved
in [ONEBOARD_TASK_NOTES.md](ONEBOARD_TASK_NOTES.md).

## Automated QA evidence

The repository passed the current complete suite during public-source audit
validation:

```text
.venv\Scripts\python.exe -m pytest .\tests
210 passed, 1 Python 3.15-targeted locale deprecation warning
```

The suite includes the first-run audio tuple contract, settings-write failure,
setup-while-running guard, bounded-stream eviction, bracketed translation result,
synchronized Clear actions, safe checked-in defaults, credential/log redaction,
FunASR provenance, runtime pruning and notice preservation, README customer path,
and manual-only release workflow regressions. Python compile checks and
`git diff --check` also pass.

A hardened dirty-preview stage passed its offline launcher smoke test with bundled
Python 3.12.5, Qt offscreen rendering, application/native imports, a real
torchaudio resample, Silero VAD construction, and a spawned ASR worker using the
bundled interpreter. It reported CPU PyTorch and no CUDA. The current stage
excluded the test-only stack and package test trees, preserved all 307
inventoried dependency notice paths, and included the update module and project
notices. Its
`dirty_preview: true` manifest makes it QA evidence; the same smoke test is a
mandatory part of every clean build.

The cached Whisper Small model was also loaded directly on CPU with `int8` and
explicit English selection while hub access was forced offline. This checks the
new base fallback without downloading a model.

The current machine-level readiness probe found:

- Windows audio, faster-whisper runtime, Whisper Small cache, and Silero VAD ready.
- CPU-only execution available, with the intended non-blocking performance advice.
- Ollama installed, but its local API is unavailable and the required
  `qwen3:4b-instruct-2507-q4_K_M` model cannot yet be confirmed. Start is therefore
  correctly blocked until the user starts Ollama and explicitly approves any model
  pull.

## Manual QA matrix

| Area | Automated evidence | Release-candidate manual status |
| --- | --- | --- |
| Source launch | `main.py` routes to `oneboard_app.run()` and import/controller tests pass. | Open `start.bat` from a clean checkout and confirm the OneBoard window. |
| Portable launch/relocation | Bundled launcher smoke passed with no developer Python on `PATH`, an unrelated working directory, and invalid external `PYTHONHOME`/`PYTHONPATH`. | Rebuild, extract to a path containing spaces on a clean Windows user/VM, and launch the EXE. |
| First run and persistence | Setup/readiness state tests pass. | Complete, cancel, reopen, restart, upgrade, and uninstall-preservation flows. |
| EN -> VI / VI -> EN / swap | Preset and controller tests verify explicit source, ASR hint, and opposite target. | Exercise both directions with real speech and the production translation model. |
| Transcript and streaming | Tests cover accumulation, in-place interim updates, finalization, bounds, Clear, and follow behavior. | Run a long session, scroll back, resume follow, export, and inspect punctuation/order. |
| Missing model / Ollama unavailable | Readiness tests cover missing/unavailable states and explicit consent. | Exercise with empty caches, stopped Ollama, failed pull, cancellation, and retry. |
| Audio missing/change | Readiness and setup logic are covered; the production tuple contract has a regression test. | Remove/change the selected device while stopped and running; test loopback and optional microphone. |
| Stop/Start and shutdown | Controller tests cover lifecycle branches. | Repeat Start/Stop, close during startup/stop, and restart after errors over a long session. |
| Advanced, logs, subtitles, export | Existing panel remains wired and import/controller tests pass. | Open every retained control, verify log/error paths, subtitles, benchmark, and transcript export. |
| Installer/uninstall | Inno configuration is statically reviewed. | Blocked here because Inno Setup ISCC is absent; install, upgrade, uninstall, shortcuts, and preserved data need VM testing. |

## Packaging audit

The intended customer launch path is:

```text
OneBoardLiveTranslate.exe
  -> bundled runtime\python.exe
  -> app\oneboard_launch.py
  -> main.main()
  -> oneboard_app.run()
```

The source path is `start.bat -> .venv\Scripts\python.exe main.py` and reaches the
same product layer. The customer stage excludes Git metadata, the developer virtual
environment, repository tests/docs/build scripts, `start.bat`, `update.bat`,
`install.*`, user settings, logs, transcripts, and downloaded model caches. Writable
state is stored under `%LOCALAPPDATA%\OneBoardLiveTranslate` unless an absolute
`ONEBOARD_DATA_DIR` override is supplied. Customer packages never invoke Git, pip,
or the upstream updater, and no multi-GB model is silently bundled or downloaded.

The launcher metadata inspected in the hardened preview is correctly branded:

- File description and product: `OneBoard Live Translate`
- Company: `OneBoard`
- Executable/identifier: `OneBoardLiveTranslate`
- Product version in the inspected QA preview: `0.2.0-rc1` (revoked for artifacts)
- File version: `0.2.0.0`
- Architecture marker: `win-x64`
- `models_bundled: false`

Any future portable artifact must use its approved versioned filename. Its
`distribution.json` must name the exact source commit and record
`dirty_preview: false`. It must contain `LICENSE`,
`LICENSES/FunASR-MIT.txt`, `LICENSES/LiveTranslate-MIT.txt`, `THIRD_PARTY_NOTICES.md`,
`dependency-inventory.json`, `runtime-requirements.txt`, `READ_ME.txt`, the
branded launcher, `app/`, and `runtime/`.

Every published binary release must correspond to an exact Git tag. For example,
tag `v1.0.0` must identify the precise clean source used for the matching ZIP and
installer; the tagged corresponding source and the same license/notices must be
published as one release set. Record the resolved tag commit in
`distribution.json`. A changed binary requires a new version and tag.

The hardened preview is approximately 1.35 GiB and records 114 copied Python
distributions after pruning pytest, pluggy, and iniconfig. The final clean build
must still be inspected from its own `runtime-requirements.txt` and
`dependency-inventory.json`, because dependency ranges are open and a future
resolution can differ.

`packaging/OneBoardLiveTranslate.iss` is prepared for Inno Setup 6.3 or later. It
defines a per-user x64 installation, Start Menu shortcut, optional Desktop shortcut,
normal uninstall support, version metadata, and optional OneBoard `.ico` input.
User data is outside `{app}` and has no uninstall-delete rule. ISCC is not installed
or available on `PATH`, so no installer or uninstall test was produced. The launcher
and installer also still need an approved icon and publisher signing for production.

## Exact clean CPU release commands

Run these in an authorized clean OneBoard developer checkout on Windows x64. They
resolve dependencies from the configured package indexes and therefore require
network access. The builder itself does not download tools, models, or dependencies.
Before running them, assign a new approved `VERSION` and `WINDOWS_VERSION` in
`version.py` and commit that change.

```powershell
git switch oneboard-dev
git status --short
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -r .\requirements.txt "yasbd-lib>=0.15,<1.0" pytest
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest .\tests
git diff --check
git status --short
$ReleaseVersion = & .\.venv\Scripts\python.exe -B -c "from version import VERSION; print(VERSION)"
powershell -NoProfile -ExecutionPolicy Bypass -File .\build_oneboard_release.ps1 -Version $ReleaseVersion
git status --short
Get-FileHash ".\release\OneBoardLiveTranslate-$ReleaseVersion-win-x64.zip" -Algorithm SHA256
```

Before running these commands, assign and commit a new approved `VERSION` and
`WINDOWS_VERSION` in `version.py`; the builder rejects ZIPs/installers for revoked
`0.2.0-rc1`. All `git status --short` commands must produce no output. The package
is built only after the full suite succeeds. The builder's tested pruning policy excludes
pytest, pluggy, iniconfig, and installed package test trees from the staged customer
runtime. Do not use `-AllowDirty` for a release. Use a separately prepared and
validated runtime for a GPU edition; the CPU command above does not promise
customer GPU acceleration.

If Inno Setup 6.3+ is already available, build both the portable ZIP and installer
from the same verified stage:

```powershell
$ReleaseVersion = & .\.venv\Scripts\python.exe -B -c "from version import VERSION; print(VERSION)"
powershell -NoProfile -ExecutionPolicy Bypass -File .\build_oneboard_release.ps1 -Version $ReleaseVersion -Iscc 'C:\Tools\Inno Setup 6\ISCC.exe' -Icon 'C:\Assets\OneBoard.ico'
Get-FileHash ".\release\OneBoardLiveTranslate-Setup-$ReleaseVersion.exe" -Algorithm SHA256
```

Do not install Inno Setup, signing tools, or system-wide build tools from the build
script. Full packaging details and limitations are in [PACKAGING.md](PACKAGING.md).

## Licensing disposition

OneBoard Live Translate is licensed under `GPL-3.0-only`, with the complete GPL
text in `LICENSE`. The exact upstream LiveTranslate MIT license and copyright
notice are preserved in `LICENSES/LiveTranslate-MIT.txt`; the verified vendored
FunASR source notice is preserved in `LICENSES/FunASR-MIT.txt`. The release
builder copies these files, the CPython license, installed wheel license/notice
files, dependency metadata, and `THIRD_PARTY_NOTICES.md`; model weights are
separate and are not covered by the Python-package inventory.

The legal audit is an inventory, not universal legal clearance. The public PyQt6
wheel reports `GPL-3.0-only`, which is compatible with the chosen open-source
distribution strategy; PyQt6 is retained, and neither a PySide6 migration nor a
commercial PyQt license is required for this strategy. PyAV/FFmpeg and codec
configuration, the broad copied native runtime, and Qt third-party components
still need publisher review. Whisper/faster-whisper model weights, Silero VAD,
FunASR/SenseVoice/Fun-ASR-Nano models, ModelScope/Hugging Face artifacts, and the
Qwen/Ollama translation model require separate model-version and use-case review
before distribution or guided download is approved. The vendored `funasr_nano/`
source provenance and MIT notice are now verified; any source change must be
re-audited. Any future GPU bundle requires a separate audit. See
[RELEASE_LICENSING_REVIEW.md](RELEASE_LICENSING_REVIEW.md) and
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for the detailed findings and
source links.

## Remaining issues and manual release work

1. Record and independently verify the clean ZIP SHA-256 and smoke report produced
   from the Phase 2.8 commit. Never publish a dirty-preview stage.
2. Install or provide Inno Setup 6.3+ manually if an installer is required, then
   run install/upgrade/uninstall QA in a clean VM. ISCC was not installed by this
   work.
3. Complete manual review of all native runtime, PyAV/FFmpeg codec, downloaded
   FunASR/SenseVoice model, and other model licenses. Preserve the verified
   vendored-source notice. Review any future GPU runtime as a separate artifact.
4. Run the manual QA matrix with Ollama running and the exact approved Qwen model,
   plus failure/cancellation tests with empty caches and unavailable services.
5. Supply an approved OneBoard `.ico`, code-signing certificate, signing procedure,
   artifact hashes, and publisher/recovery process.
6. Configure a real OneBoard HTTPS release manifest only when hosting and trust
   policy exist. Update checks remain safely disabled; the current discovery format
   has no manifest signature or binary verification/installation mechanism.
7. Runtime requirements use open ranges. Imports and a real torchaudio resample
   passed, and each build writes its exact inventory, but lock and validate the
   production dependency set before claiming reproducible releases.
8. The inherited pipeline can finish a buffered speech segment during shutdown.
   OneBoard performs the potentially long stop outside the GUI thread and routes UI
   updates through Qt signals, but some inherited pipeline reads still touch Qt
   widget state from worker paths. Exercise close/stop under active speech in the
   manual matrix before publication.

The first-run audio test had a confirmed adapter bug: production capture returns a
`(samples, mic_rms)` tuple while the wizard treated the result as a NumPy array.
Phase 2.8 corrects that contract and adds a regression test. The hardening pass also
removes an exposed checked-in fallback, aligns base defaults with Whisper Small
CPU and EN-to-VI Ollama, and makes generated release-artifact cleanup narrowly
scoped. These fixes passed the full suite and unarchived package staging smoke;
the separate manual and artifact-licensing gates above still block release.

## Remaining `LiveTranslate` references

No customer-visible legacy product string was found in the inspected packaged UI
stage. The READMEs now identify OneBoard first, give the OneBoard executable path,
and state that upstream releases and `update.bat` are not customer update paths.
The GitHub workflow is manual, calls only the OneBoard builder, uploads a
workflow-run artifact, and cannot publish on a tag.

Remaining repository references are deliberate upstream or developer references:

- `README.md` and `README_zh.md`: links, screenshot descriptions, and
  acknowledgement credit the upstream LiveTranslate project.
- `build_release.ps1`, `start.bat`, `update.bat`, `install.ps1`, `REMOTE_ASR.md`, and
  remote-ASR docstrings: inherited developer workflow text. These files are excluded
  from OneBoard customer packages; `update.bat` must remain developer-only.
- Internal `LiveTranslate.*` logger namespaces and `LiveTranslateApp` class names:
  allowed by the minimal-fork policy and not customer branding.
- Dependency metadata that credits or links to upstream LiveTranslate: attribution,
  not OneBoard product branding.

## Repository state

The audit was performed on `oneboard-dev`. Both protected references remained at
the upstream baseline:

```text
main          190ef027f38e577b0d2ecd06058ff6cbd236496b
upstream/main 190ef027f38e577b0d2ecd06058ff6cbd236496b
```

Phase 2 changes exist only on `oneboard-dev`; nothing was pushed. Before declaring
the hardening commit complete, run `git diff --check`, review staged and unstaged
diffs, commit only the intended Phase 2.8 files, and confirm `git status --short` is
empty. Generated `release/`, models, caches, logs, transcripts, virtual environments,
and `user_settings.json` remain ignored and must not be committed.

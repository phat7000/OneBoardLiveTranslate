# OneBoard Live Translate Phase 2 Final Report

> Historical RC1 record. For the current RC3 decision, use
> `RELEASE_LICENSING_REVIEW.md` and `RC3_RUNTIME_AUDIT.md`.

Report date: 2026-09-10

Licensing decision updated: 2026-09-11

GPL release validation updated: 2026-09-13

Public-source audit validation updated: 2026-09-14

Historical release candidate: `0.2.0-rc1` (`0.2.0.0` Windows file version), revoked

Target: Windows x64, CPU base distribution

## Release decision

**HOLD for customer publication.** The Phase 2 implementation, automated test
suite, portable packaging path, and unarchived staging smoke are complete within
the available build environment. The historical candidate is revoked. Promotion
remains on hold until the clean-machine manual QA matrix, installer validation,
and licensing gates in this report are cleared.

The final project-license decision is `GPL-3.0-only` open-source distribution
with PyQt6 retained. A PySide6 migration and a commercial PyQt license are not
required for this chosen GPL-compatible release strategy. This resolves the
former PyQt distribution-choice gate, but not the remaining third-party,
native-library, codec, and model audits. A 2026-09-13 follow-up verified the
vendored FunASR Python-source provenance and added its MIT notice.

Status terms used throughout this report:

- **COMPLETE**: implementation and available automated validation are finished.
- **PARTIAL**: useful work is complete, but a defined part remains unfinished.
- **HOLD**: the item blocks customer/public release until the stated condition is
  resolved.

## Phase status and commits

| Phase | Status | Commit SHA | Result |
| --- | --- | --- | --- |
| 2.3 Product UX | **COMPLETE** | `392f02076047fb4133b6d914fb8a1874f43351e9` | OneBoard product window, explicit EN/VI presets, bounded two-pane transcript, Start/Stop, Clear, and Advanced access. Manual RC exercise remains in the release QA matrix. |
| 2.4 Runtime readiness | **COMPLETE** | `dbdf99b49dac79704399458d4769379f9f0293f1` | Audio, ASR runtime/model, Ollama service/model, and CPU/GPU readiness checks with explicit download actions. The current workstation still has external readiness issues described below. |
| 2.5 First-run setup | **COMPLETE** | `18c6a7c7755ce7f97012e3f86a2ba85e7e00138f` | Reopenable setup wizard and persisted completion state. A clean-profile manual exercise remains required. |
| 2.6 Windows packaging | **PARTIAL** (portable **COMPLETE**) | `d9c453e5fe70afeb577be04655861df1807390a3` | Portable runtime, branded launcher, release builder, smoke test, and Inno Setup definition are complete. The installer was not built because ISCC/Inno Setup is unavailable. |
| 2.7 Update architecture | **COMPLETE** | `87f770ef83bfaedbea0a1ea8b0016c2cdec6db71` | Configurable HTTPS OneBoard manifest discovery exists and is disabled by default. Customer UI does not pull from upstream, download an update, or execute one. |
| 2.8 QA, licensing, and hardening | **PARTIAL / HOLD** | `704e385a0fd2f55d653e27257faedf2792d1d702` | Automated and repository audits are complete, and the project license is finalized as `GPL-3.0-only`. Manual end-to-end QA, artifact-level third-party/model licensing, installer validation, icon, and signing remain open release gates. |

The OneBoard branding foundation is commit
`5c1f065fa9a1d5b71113ce6d2b1a3814b7421d0f`. The permanent development
guidelines used for these phases are recorded by commit
`801d5d8a3c3e5d515450c411b9877224cb83a6d9`.

## Historical revoked release artifact

| Property | Value |
| --- | --- |
| Former checkout path | `release/OneBoardLiveTranslate-0.2.0-rc1-win-x64.zip` (removed) |
| Size | `473,774,572` bytes (`451.8 MiB`) |
| SHA256 | `293F28FF5F50C40919EB1221D1E6A3525786745BE8E40E9A0233A8689C10E0C4` |
| Source commit | `704e385a0fd2f55d653e27257faedf2792d1d702` |
| Exact source tag | None; this RC predates the final tag-mapping policy and is not approved for publication |
| Manifest state | `dirty_preview: false`; `models_bundled: false` |
| Archive verification | ZIP CRC passed; `33,516` entries; no duplicate or forbidden files found |

The portable artifact is a revoked release candidate, not an approved customer
release. It contains the credential removed from the current tree and predates
the FunASR provenance cleanup; no retained copy may be published or shared.
No installer artifact exists because ISCC/Inno Setup was not available. The
artifact was inspected and hashed without rebuilding it while this report was
created. It predates the GPL project-license layout and exact-tag policy recorded
here, so it must not be published or treated as the customer package for this
decision; a future release must be rebuilt from its exact tagged source.

Every future published binary must correspond to one exact Git tag. For example,
tag `v1.0.0` identifies the precise source used for the matching `v1.0.0` ZIP and
installer and their matching license/notices. The tagged source and corresponding
source materials must remain available with the release; a changed binary needs
a new version and tag. See the detailed policy in
[`RELEASE_LICENSING_REVIEW.md`](RELEASE_LICENSING_REVIEW.md).

## Delivered implementation

OneBoard-specific product modules include `oneboard_app.py`, `oneboard_ui.py`,
`oneboard_transcript_view.py`, and `oneboard_presets.py`. Runtime readiness and
setup are isolated in `oneboard_readiness.py` and `oneboard_setup.py`. Packaging
and runtime support are implemented in `oneboard_launch.py`, `oneboard_paths.py`,
`version.py`, `build_oneboard_release.ps1`, and `packaging/`. The customer update
abstraction is in `oneboard_updates.py` and documented in
`ONEBOARD_UPDATES.md`.

The primary UI provides explicit English to Vietnamese and Vietnamese to English
directions, audio selection, Start/Stop, status, transcript clearing, and access
to the complete inherited Advanced Control Panel. Source and translation history
accumulate in separate bounded, wrapping, scrollable regions. Interim text is
updated in place so it does not create duplicate transcript entries.

Small integration changes were required in upstream-owned files:

- `main.py` retains inherited orchestration as `upstream_main()`, routes the
  normal entry point to the OneBoard product window, and uses the OneBoard data
  path adapter for mutable logs and transcripts.
- `control_panel.py` retains the complete Advanced panel and uses the persistent
  data path for settings and transcripts.
- `model_manager.py` uses the same cache-path adapter without changing model
  management behavior.
- Dialog, subtitle, and localized display strings use centralized values from
  `branding.py`; internal logger namespaces and upstream attribution remain.
- `config.yaml` supplies safe OneBoard defaults for Whisper Small CPU/int8,
  explicit English to Vietnamese, and local Ollama/Qwen translation while
  preserving other languages and engines in Advanced.

No ASR, VAD, audio-capture, translation, worker, or model-download algorithm was
rewritten for the OneBoard layer. Detailed integration rationale remains in
`ONEBOARD_TASK_NOTES.md`.

## Automated test results

These results combine the Phase 2.8 hardening evidence with the public-source
audit validation run on 2026-09-14. The audit reran the full repository suite,
syntax/import checks, focused packaging/license tests, and an unarchived staging
smoke without building a replacement release candidate.

| Check | Result |
| --- | --- |
| Full Python suite: `.venv\Scripts\python.exe -m pytest .\tests` | **PASS** — `210 passed`, with one `locale.getdefaultlocale` deprecation warning targeting Python 3.15 |
| Dependency consistency: `.venv\Scripts\python.exe -m pip check` | **PASS** |
| Python compile/import validation | **PASS** |
| Repository whitespace/error check: `git diff --check` | **PASS** |
| Offline cached Whisper Small load on CPU, `int8`, explicit English | **PASS** |
| Packaged native imports, torchaudio resample, Qt, Silero VAD, and spawned multiprocessing ASR worker | **PASS** |
| Packaged OneBoard UI initialization from bundled runtime and an unrelated working directory | **PASS** |
| Current unarchived staging smoke and notice-path audit | **PASS** — 307/307 inventoried dependency notices present; no ZIP or installer created |
| Historical RC1 ZIP integrity, duplicate-path, and forbidden-file audit | **PASS (historical only)** — candidate revoked and removed from the checkout |

The test suite covers presets, swapping, transcript accumulation and bounds,
in-place streaming updates, Clear, controller lifecycle paths, first-run state,
readiness branches, model-download consent, settings-write failure, setup while
running, safe checked-in defaults, update behavior, packaging, and customer-path
regressions.

## COMPLETE items

- OneBoard simplified UI and bounded two-pane live transcript behavior.
- Explicit EN to VI and VI to EN source/ASR/target presets.
- Access to the full upstream Advanced Control Panel.
- Runtime readiness checks and explicit model-download actions.
- Reopenable first-run setup wizard and persisted completion state.
- Portable Windows x64 CPU packaging, branded launcher, manifest, inventory,
  notices, and automated packaged-runtime smoke checks.
- Customer update abstraction with checks disabled until real OneBoard release
  infrastructure exists.
- Repository-level automated suite, packaging audit, licensing inventory, and
  hardening fixes recorded through Phase 2.8.
- Final `GPL-3.0-only` open-source project-license decision, with PyQt6 retained
  and the upstream LiveTranslate MIT license preserved separately.

## PARTIAL items

- Windows installer: the Inno Setup definition is ready, but no installer was
  built or tested because ISCC/Inno Setup is unavailable on this workstation.
- Manual release QA: automated coverage is complete, but real audio, model,
  long-session, relocation, failure, upgrade, and uninstall exercises remain.
- Licensing: the project license and vendored FunASR source provenance are
  finalized, but dependency, native-library, codec, and model inventories are
  not universal legal clearance.
- Reproducibility: each package records its exact dependency inventory, but open
  dependency ranges mean a future clean resolution may not be byte-for-byte
  identical.
- Updates: discovery architecture exists, but there is no production endpoint,
  manifest signature, binary-verification, download, install, rollback, or
  recovery service. Checks remain disabled by design.

## HOLD items

- **Customer/public release promotion is on HOLD** until every manual QA and
  licensing gate below is cleared.
- **Artifact-level licensing remains on HOLD** until the exact native libraries,
  PyAV/FFmpeg codecs, downloaded FunASR/SenseVoice models, other models, and
  required source/notices have been reviewed for the final package. Any future
  GPU bundle requires a separate review.
- **Installer release is on HOLD** until Inno Setup is available and the resulting
  installer passes clean-machine install, upgrade, uninstall, shortcut, and user
  data preservation tests.
- **Production signing and visual identity are on HOLD** pending the final
  OneBoard `.ico` file and a code-signing certificate/procedure.

## Manual actions still required

- Extract and run the portable RC on a clean Windows x64 user profile or VM,
  including a path containing spaces and a machine without developer Python or
  Git.
- Start Ollama and explicitly approve installation of
  `qwen3:4b-instruct-2507-q4_K_M` (approximately 2.5 GB) if it is not present.
- Exercise real English to Vietnamese and Vietnamese to English speech, device
  selection/change, model-missing and Ollama-unavailable paths, failed or
  cancelled model pulls, repeated Start/Stop, close during active speech, restart,
  persisted settings, subtitles, logs, benchmark, Advanced settings, and export.
- Run a long transcript session; verify interim replacement, ordering,
  punctuation, bounded history, scroll-back, resuming live follow, and Clear.
- Make Inno Setup 6.3 or later available, build the installer, then test clean
  install, upgrade, shortcuts, uninstall, and preservation of user data on a VM.
- Supply and validate the final OneBoard icon, code-signing certificate, signing
  procedure, publisher identity, and artifact verification process.
- Configure a real HTTPS OneBoard update manifest only after hosting, trust,
  verification, installation, rollback, and recovery policies are approved.
- Complete and document the artifact-level third-party and model license review.

The current workstation readiness probe found Windows audio APIs, the
faster-whisper runtime, cached Whisper Small, and Silero VAD ready. CPU-only
operation is available with a non-blocking performance advisory. No usable audio
device was available, and Ollama was installed but its local API was not
responding, so the required Qwen model could not be confirmed. These are external
machine/manual readiness conditions rather than automated-test failures.

## Licensing decision and remaining blockers

This inventory is not legal advice and does not establish commercial clearance.
OneBoard Live Translate is licensed under `GPL-3.0-only`; the upstream
LiveTranslate MIT license and attribution are preserved in
`LICENSES/LiveTranslate-MIT.txt`, and the verified vendored FunASR source MIT
notice is preserved in `LICENSES/FunASR-MIT.txt`. Models are not bundled in the
base ZIP, but separate download does not by itself clear their permitted use.

- The current public PyQt6 wheel reports `GPL-3.0-only`. Riverbank describes
  PyQt6 as GPLv3/commercial dual licensed and not LGPL. This is compatible with
  the chosen `GPL-3.0-only` open-source distribution strategy, so PyQt6 is
  retained; no PySide6 migration or commercial PyQt license is required for this
  strategy. The final package must still satisfy all applicable GPL obligations.
- The complete Qt wheel and its third-party components require review of the
  applicable LGPLv3 notice, source, relinking, installation-information, and
  module-specific obligations for the exact artifact.
- PyAV's Windows wheel contains FFmpeg and codec libraries with separate terms.
  PyAV metadata alone does not clear FFmpeg, x264, x265, LAME, OpenCORE-AMR,
  dav1d, Opus, SVT-AV1, VPX, WebP, MinGW runtime, or other bundled libraries.
- The exact runtime also requires review of soxr, libsndfile, OpenMP/runtime
  libraries, Microsoft redistributables, and all other native wheels and DLLs.
- Vendored `funasr_nano/` provenance is verified against FunASR commit
  `335eb1ea6156bc353283e21ae121a2224aa79175`; preserve the documented mapping and
  `LICENSES/FunASR-MIT.txt`, and re-audit any source change.
- The exact revision or digest and archived license/model card must be approved
  for faster-whisper Small and the Ollama Qwen tag. The current Qwen tag displays
  Apache-2.0, and faster-whisper Small displays MIT, but neither is pinned to an
  immutable approved release record.
- SenseVoice and FunASR model sources expose inconsistent or additional model
  terms, including `model-license` metadata and the FunASR model agreement. Every
  selected hub, nested model, revision, remote-code component, and use case needs
  review.
- Any future GPU distribution requires a separate inventory and review of its
  exact PyTorch, CTranslate2, CUDA, cuDNN, and NVIDIA runtime components.

The detailed evidence and source links are in
[`RELEASE_LICENSING_REVIEW.md`](RELEASE_LICENSING_REVIEW.md) and
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

## Known risks and remaining legacy references

No OneBoard regression is known from the automated suite. The inherited pipeline
can finish buffered speech during Stop, and some inherited worker paths read Qt
widget state. Close and repeated Start/Stop under active speech therefore remain
part of the manual stress matrix. The single Python 3.15-targeted locale
deprecation warning also remains.

No customer-visible legacy product name was found in the inspected packaged UI.
Remaining `LiveTranslate` references are deliberate: upstream links, screenshot
descriptions and acknowledgement in the READMEs; inherited developer scripts and
documentation excluded from the customer package; internal logger/class names;
and preserved dependency/upstream attribution.

## Repository state for this public-source audit

| Item | State |
| --- | --- |
| Development branch | `oneboard-dev` |
| Audit base before these changes | `0ee9e5705129c60622616ebc2361f0a8a03578d3` |
| Public-source audit result | This commit (`Prepare clean public source release`) |
| `main` | `190ef027f38e577b0d2ecd06058ff6cbd236496b` — unchanged upstream baseline |
| `upstream/main` | `190ef027f38e577b0d2ecd06058ff6cbd236496b` — unchanged upstream baseline |
| Worktree before the public-source audit | Clean |
| Audit commit scope | Current-source credential removal, FunASR provenance and notice, package/log/documentation hygiene, and regression tests |
| Expected worktree after the audit commit | Clean; `git status --short` produces no output |
| Push state | Nothing pushed by Phase 2 work or the public-source audit |

Generated releases, models, virtual environments, caches, logs, transcripts,
runtime user settings, and other ignored artifacts remain outside Git.

## Exact clean-build commands

Run these commands in an authorized clean OneBoard developer checkout on Windows
x64. They require Python 3.12 x64 and network access for dependency installation.
The build script itself does not install system-wide tools or silently download
models. Do not use `-AllowDirty` for a release. Before running them, assign a new
approved `VERSION` and `WINDOWS_VERSION` in `version.py` and commit that change.

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

First assign and commit a new approved `VERSION` and `WINDOWS_VERSION` in
`version.py`; the builder rejects ZIPs/installers for revoked `0.2.0-rc1`. Every
`git status --short` command must produce no output. If Inno Setup 6.3 or later
and the approved icon are already available, build the installer from the same
verified stage with:

```powershell
$ReleaseVersion = & .\.venv\Scripts\python.exe -B -c "from version import VERSION; print(VERSION)"
powershell -NoProfile -ExecutionPolicy Bypass -File .\build_oneboard_release.ps1 -Version $ReleaseVersion -Iscc 'C:\Tools\Inno Setup 6\ISCC.exe' -Icon 'C:\Assets\OneBoard.ico'
Get-FileHash ".\release\OneBoardLiveTranslate-Setup-$ReleaseVersion.exe" -Algorithm SHA256
```

See [`PACKAGING.md`](PACKAGING.md) for packaging behavior and limitations.

## Next Actions

1. Test portable RC on a clean Windows machine/VM.
2. Resolve the remaining native-library, FFmpeg/codec, and model license reviews.
3. Create an exact release tag and publish matching corresponding source,
   binaries, licenses, and notices as one release set.
4. Build and test Windows installer after ISCC/Inno Setup is available.
5. Perform real EN→VI and VI→EN long-session QA.
6. Provide final OneBoard icon and code-signing certificate.
7. Promote RC to release only after all HOLD items are cleared.

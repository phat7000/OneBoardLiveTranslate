# OneBoard Live Translate release licensing review

Review date: 2026-09-14

Project-license decision updated: 2026-09-11

Scope: repository dependencies, the current Windows CPU packaging design, the
current prepared `.venv`, and model identifiers reachable from the application.

## Result

**Project license: `GPL-3.0-only`. Phase 2.8 artifact licensing status remains
PARTIAL / HOLD pending the dependency, native-library, codec, and model reviews
below. Vendored FunASR Python-source provenance is VERIFIED.**

This review does not establish commercial legal clearance. The upstream MIT
license is preserved in `LICENSES/LiveTranslate-MIT.txt`, the vendored FunASR MIT
license is preserved in `LICENSES/FunASR-MIT.txt`, and model caches are excluded
from the base package. The final distribution decision is to keep PyQt6
and release OneBoard Live Translate as free and open-source software under
`GPL-3.0-only`. The public PyQt6 wheel's `GPL-3.0-only` terms therefore no longer
form a separate blocker for the chosen strategy. A PySide6 migration and a
commercial PyQt license are not required for this release strategy.

The following artifact-level release gates remain open:

1. Runtime dependency versions are not locked. The pre-hardening inspected build
   contained 117 Python distributions and broad native wheels. The hardened
   copier removes the pytest/iniconfig/pluggy development stack and installed
   package test trees, but the remaining environment is still large and
   resolution-dependent. This creates a build-dependent license surface.
2. The full `PyQt6-Qt6` wheel is copied. It contains many Qt modules and native
   DLLs beyond the modules visibly used by this application. Qt LGPLv3 and
   third-party notice/source/relinking obligations have not been verified for
   the exact artifact.
3. PyAV 18.1.0 is present transitively. Its Windows wheel contains FFmpeg plus
   x264, x265, LAME, OpenCORE-AMR, dav1d, Opus, SVT-AV1, VPX, WebP, MinGW runtime,
   and other DLLs. Runtime inspection reports FFmpeg as "LGPL version 3 or
   later", but the separately shipped codec libraries have their own terms.
   Metadata that labels only the PyAV wrapper BSD-3-Clause is insufficient.
4. Optional FunASR/SenseVoice model repositories show conflicting or ambiguous
   license labels, while the FunASR project publishes a custom, revisable model
   agreement. Exact model repositories and revisions are not pinned.
5. Any future GPU bundle has a different dependency and EULA surface and requires
   a separate, artifact-specific review.

The `GPL-3.0-only` decision resolves the project/PyQt distribution choice only.
This report does not determine that corresponding-source, notice, installation-
information, codec, patent, model, or other obligations have been satisfied. A
qualified reviewer must approve the exact release artifact.

### Vendored FunASR Python source — VERIFIED

The complete tracked `funasr_nano/` directory was compared by Git blob and file
content with the authoritative `modelscope/FunASR` repository. At FunASR commit
`335eb1ea6156bc353283e21ae121a2224aa79175`, all five corresponding files are
under `funasr/models/fun_asr_nano/`. All five were byte-identical when imported
by inherited LiveTranslate commit `b549e858e37d684e3ca48f247901e439c580c3bb`.
Four remain byte-identical. Only `funasr_nano/model.py` differs, through the
documented model-loading change in inherited LiveTranslate commit
`d536d55c71d040d654292cae8c716266d71c6779`.

The pinned core directory has no nested license or notice, so the FunASR root MIT
license applies: `Copyright (c) 2025 FunASR`. Its complete text is preserved in
`LICENSES/FunASR-MIT.txt`, included in packages, and mapped file-by-file in
`THIRD_PARTY_NOTICES.md`. The separate FunASR model agreement applies to model
weights and derivatives; optional downloaded models therefore remain on HOLD.

## Evidence reviewed

- `requirements.txt` contains open lower bounds rather than a lock file.
- `packaging/build_oneboard.py` copies CPython, the standard library, and the
  prepared runtime packages while pruning known test-only packages and test
  trees. It deliberately preserves package license/notice files and generates
  `runtime-requirements.txt` plus `dependency-inventory.json` for each artifact.
- The current CPU package manifest says `models_bundled: false`; package docs
  state that Ollama and GPU drivers are not bundled.
- The inspected environment currently includes PyQt6 6.11.0
  (`GPL-3.0-only`), PyQt6-Qt6 6.11.2 (`LGPL v3`), soxr 1.1.0
  (`LGPL-2.1-or-later`), yasbd-lib 0.16.2 (`MPL-2.0`), and a CPython 3.12
  runtime. Versions in a future build may differ.
- Some installed metadata fields are empty or ambiguous. Examples include
  `kaldiio`; `torch-complex` reports `UNKNOWN` in one field while also carrying
  an Apache license classifier. Other metadata fields contain full composite
  notices that describe bundled native libraries rather than a single SPDX
  expression.
- The current CPU PyTorch distribution contains Intel/OpenMP and other native
  components. The NumPy/SciPy wheels contain their own BLAS/runtime notices.
  Their installed license files are retained, but fulfillment has not been
  independently checked.
- CPython's `LICENSE.txt` is copied into the runtime. The builder also copies
  Microsoft Visual C++ runtime DLLs; their applicable redistribution terms need
  artifact-level review.
- The vendored FunASR source comparison is pinned to authoritative commit
  `335eb1ea6156bc353283e21ae121a2224aa79175`. The upstream root `LICENSE` Git
  blob is `26b5e09e91ef525769c209eabcf58a6e2448ddce`, and the canonical license SHA-256
  is `f382b62dcc61fc566b9215b1e3b604b539bfd96ed52ae1eeff5090f6dc176057`.

Package metadata is supplied by package publishers. It can lag the actual wheel,
omit embedded libraries, or describe only a wrapper. The generated inventory is
useful evidence, but is not an SBOM, source offer, or legal conclusion.

## Model inventory

| Model/runtime | Repository identifier used by code | Base package | Current finding | Required release action |
| --- | --- | --- | --- | --- |
| Silero VAD | Asset inside `silero-vad` wheel | Included | Current project/wheel identifies MIT | Retain its installed license; verify the exact wheel in the final artifact. |
| Whisper Small | `Systran/faster-whisper-small` | Downloaded after user action | Current model card says MIT; upstream conversion source is OpenAI Whisper | Pin an approved revision/digest and archive its model card/license for the release record. |
| Qwen translation | `qwen3:4b-instruct-2507-q4_K_M` | Downloaded through external Ollama | Exact current tag shows Apache-2.0 and digest prefix `0edcdef34593`; the app uses a mutable tag | Record the resolved full digest and embedded license after pull; do not host/bundle it without a separate redistribution review. |
| Ollama runtime | Local service/API | Not bundled | Ollama source currently MIT; its installer/runtime is an external prerequisite | Keep it external for this release and link only to the official flow; review installer terms if future packaging changes. |
| SenseVoice Small | `iic/SenseVoiceSmall` or `FunAudioLLM/SenseVoiceSmall` | Optional download | ModelScope has displayed Apache-2.0; Hugging Face currently displays `model-license`; FunASR publishes a custom model agreement | Manual legal review of the selected hub and immutable revision before commercial use/redistribution. |
| Fun-ASR-Nano | `FunAudioLLM/Fun-ASR-Nano-2512` | Optional download | Hub currently displays Apache-2.0; model uses nested Qwen3-0.6B weights; FunASR also publishes its model agreement | Review and pin the ASR model, nested Qwen weights, remote code, and all notices together. |
| Fun-ASR-MLT-Nano | `FunAudioLLM/Fun-ASR-MLT-Nano-2512` | Optional download | Same unresolved agreement/provenance boundary as Fun-ASR-Nano | Review and pin before enabling it in a supported commercial configuration. |
| Anime-Whisper | `litagin/anime-whisper` | Optional download | Current model card says MIT; it is derived from another Whisper model and a named training dataset | Review the exact checkpoint, base-model chain, dataset terms, and intended use. |

Downloading a model onto the customer's machine instead of bundling it reduces
the base installer contents; it does not prove that every intended use is
permitted. License text and model-card metadata can also change at an unpinned
hub revision.

## Runtime and GPU boundary

The current package is a CPU build. It contains CPU PyTorch/torchaudio and no
NVIDIA driver, CUDA toolkit, cuDNN package, or downloaded GPU model cache. The UI
may report GPU availability, but that does not convert this artifact into a GPU
distribution.

Any future GPU artifact needs a fresh dependency resolution and binary scan. The
publisher must review the licenses/EULAs and redistribution rights for the exact
PyTorch, CTranslate2, CUDA, cuDNN, and NVIDIA runtime files selected for that
artifact. Findings from this CPU build must not be carried over.

## Binary/source release mapping policy

Every published binary release must correspond to one exact, immutable Git tag.
For example, release `v1.0.0` consists of the exact source at tag `v1.0.0`, the
portable ZIP and installer built from that clean tagged commit, and the matching
`LICENSE`, `LICENSES/FunASR-MIT.txt`, `LICENSES/LiveTranslate-MIT.txt`,
`THIRD_PARTY_NOTICES.md`, and artifact inventories. The tag's source must remain
publicly available with the binary release in a form that satisfies the GPL
corresponding-source requirements.

Record the tag in the release record and record its resolved commit in
`distribution.json`. Never publish a dirty-preview build, rebuild a changed
binary under an existing tag, or mix notices from a different revision. Any
binary change requires a new version and exact tag.

## Manual release actions

- Build and convey the complete work under `GPL-3.0-only` from the exact release
  tag. Retain the PyQt6 GPL evidence, provide the corresponding source as the GPL
  requires, and ship all project, upstream, and dependency notices. The chosen
  strategy does not require a PySide6 migration or commercial PyQt license.
- Preserve the pinned `funasr_nano/` provenance mapping and
  `LICENSES/FunASR-MIT.txt`; re-audit and update both if any vendored file changes.
- Build from a clean, dedicated, locked release environment. Verify that the
  pruning policy removed development-only files, remove further unused native
  modules only where technically safe, then regenerate and review the exact
  inventory.
- Scan the final staging directory, including every DLL, executable, data/model
  asset, font, codec, and installer payload. Map each item to copyright, license,
  notice, source-code/source-offer, and relinking/installation-information
  obligations as applicable.
- Review PyAV/FFmpeg and its codec DLLs, Qt and Qt third-party code, soxr,
  libsndfile, OpenMP/runtime libraries, and Microsoft redistributables with a
  qualified reviewer.
- Preserve all package license files in the artifact and add any notices or full
  license texts missing from upstream wheels. Archive corresponding source or
  valid source offers where the selected licenses require them.
- Pin approved model revisions/digests and save the license/model-card files seen
  at approval time. Re-run this check whenever a model tag, hub, runtime, or
  package version changes.
- If an Inno Setup installer is produced, review the exact compiler/stub license,
  include required notices, inspect the final installer contents, and repeat the
  clean-machine install/uninstall test.
- Obtain documented legal approval for the intended countries, distribution
  terms, and commercial model before marking licensing complete.

## Sources used for this inventory

- [Riverbank PyQt introduction and licensing](https://www.riverbankcomputing.com/software/pyqt/)
- [Riverbank commercial license FAQ](https://riverbankcomputing.com/commercial/license-faq)
- [Qt 6 licensing](https://doc.qt.io/qt-6/licensing.html)
- [Qt third-party code](https://doc.qt.io/qt-6/licenses-used-in-qt.html)
- [Python 3.12 license](https://docs.python.org/3.12/license.html)
- [PyAV repository](https://github.com/PyAV-Org/PyAV)
- [PyAV FFmpeg binary-build repository](https://github.com/PyAV-Org/pyav-ffmpeg)
- [Silero VAD license](https://github.com/snakers4/silero-vad/blob/master/LICENSE)
- [Systran faster-whisper-small model card](https://huggingface.co/Systran/faster-whisper-small)
- [Exact Ollama Qwen tag](https://ollama.com/library/qwen3:4b-instruct-2507-q4_K_M)
- [Qwen3-4B-Instruct-2507 model card](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507)
- [SenseVoiceSmall model card](https://huggingface.co/FunAudioLLM/SenseVoiceSmall)
- [FunASR model agreement](https://github.com/modelscope/FunASR/blob/main/MODEL_LICENSE)
- [Pinned FunASR source revision](https://github.com/modelscope/FunASR/commit/335eb1ea6156bc353283e21ae121a2224aa79175)
- [Pinned FunASR MIT license](https://github.com/modelscope/FunASR/blob/335eb1ea6156bc353283e21ae121a2224aa79175/LICENSE)
- [Anime-Whisper model card](https://huggingface.co/litagin/anime-whisper)
- [Ollama license](https://github.com/ollama/ollama/blob/main/LICENSE)

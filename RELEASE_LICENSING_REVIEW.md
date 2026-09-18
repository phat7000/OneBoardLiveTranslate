# OneBoard Live Translate RC3 release licensing review

Review date: 2026-09-18

Target: `0.2.0-rc3`, Windows x64 CPU portable candidate

Project license: `GPL-3.0-only`

## Decision

The RC2 redistribution blockers have a defined, automated RC3 disposition:

- PyAV and its FFmpeg/codec bundle are removed from the supported NumPy-audio
  flow instead of being relicensed or hidden.
- Qt Multimedia and its FFmpeg backend are removed; only the audited QtBase
  Widgets subset remains.
- the unnecessary cuDNN DLL is removed and known CUDA/cuDNN runtime DLLs are a
  build failure;
- the required CTranslate2/oneDNN/Intel OpenMP stack has exact provenance,
  version, hashes where applicable, and packaged license/notice material;
- all nine distributions that lacked a discoverable wheel license have pinned
  supplemental records and complete texts; and
- the builder now fails closed on a packaged Python distribution without an
  auditable license file or on reviewed native version drift.

This makes RC3 suitable for technical redistribution-candidate QA if the actual
generated artifact passes the builder, smoke and post-build audit. It is not a
legal opinion or a claim of patent, codec, model, export-control or commercial
clearance.

## Exact native decisions

### PyQt6 and Qt

PyQt6 `6.11.0` remains under `GPL-3.0-only`, matching the project's chosen
license. PyQt6-Qt6 `6.11.2` remains as replaceable shared libraries under the
wheel's LGPLv3 terms. The runtime allowlist contains only QtCore, QtGui,
QtWidgets, three platform plugins, one style plugin and three basic image
plugins. Exact QtBase `v6.11.2` attribution metadata and applicable third-party
texts are packaged from commit
`ef55f427f2c8b410d34f8a7681020a3000cf6866`.

Qt Multimedia, Qt FFmpeg, QML/Quick, unused modules and `opengl32sw.dll` are not
shipped. Any future Qt allowlist/version change is an audit failure until its
notices are deliberately updated.

### CTranslate2 CPU stack

CTranslate2 `4.8.2` is required by faster-whisper. Its official Windows build
recipe identifies oneDNN `3.1.1` and Intel oneAPI/OpenMP `2025.3.0`.
`libiomp5md.dll` is byte-identical to the official Intel OpenMP wheel file and
is hash-gated. CTranslate2, its embedded header/submodule components, oneDNN,
Intel's EULA and OpenMP third-party programs are all packaged.

The upstream CTranslate2 DLL is monolithic and was compiled with dynamically
loaded CUDA support. RC3 cannot safely remove code sections from that required
binary, but includes no CUDA runtime or cuDNN DLL and supports/advertises only
CPU operation. Rebuilding a CPU-only upstream DLL would require a separately
controlled C++ toolchain and a new binary provenance review; it is not simulated
by deleting required code.

### PyAV and media codecs

PyAV `18.1.0` existed only because faster-whisper imports its audio decoder at
module import time. OneBoard captures audio itself and always supplies NumPy
arrays, so the decoder is unreachable in supported operation. The staged
faster-whisper source is hash-checked before a minimal lazy-import patch. PyAV,
its metadata, `av.libs`, FFmpeg, x264, x265 and all other codec DLLs are absent.
The package explicitly says standalone faster-whisper media-file decoding is not
supported. This review makes no codec or patent clearance claim.

## Python distribution completeness

`dependency-inventory.json` is generated from the staged runtime, not the
developer environment. Original wheel license/notice files are preserved below
their dist-info directories. Supplemental records are version-pinned for:

`antlr4-python3-runtime`, `ctranslate2`, `flatbuffers`, `jamo`, `jieba`,
`loguru`, `sentencepiece`, `tokenizers`, and `torch-complex`.

Their full source/ref/license mapping is in `THIRD_PARTY_NOTICES.md` and enforced
in `packaging/build_oneboard.py`. A version mismatch or a dependency with neither
an installed nor supplemental license file stops the build.

## Model boundary

Downloaded Whisper, SenseVoice, FunASR, Anime-Whisper, Qwen and Ollama assets are
not in the package. The manifest records `models_bundled: false`, and downloads
require an explicit user action. Model cards, nested weights and remote service
terms remain separate review items for the user's selected model/revision. The
vendored `funasr_nano` Python source provenance and MIT notice remain pinned as
documented in `THIRD_PARTY_NOTICES.md`.

## Remaining REVIEW items for a public release

These are publisher/legal/operational reviews, not technical blockers for an
internal RC3 portable candidate:

1. Deliver matching corresponding source and an immutable source tag alongside
   any public GPL binary; no tag or release is created by this RC3 task.
2. Preserve Qt shared-library replaceability and provide the exact Qt/PyQt source
   and relinking information required for the chosen GPL/LGPL distribution.
3. Ensure the customer license presentation preserves Intel's terms for the
   separate OpenMP Redistributable, including the applicable reverse-engineering
   wording, and have qualified counsel confirm the intended distribution model.
4. Retain Microsoft runtime redistribution terms and verify any future change in
   copied Microsoft DLLs.
5. Review and pin any model revision before the publisher redistributes model
   weights; RC3 itself bundles none.
6. Treat code signing, a final icon, installer QA and clean-machine real-audio QA
   as promotion work. An unsigned executable is acceptable for internal RC QA.

Any future GPU build, new Qt module/plugin, native-wheel upgrade or reintroduced
media decoder requires a fresh artifact-specific review.

## Packaged evidence

- `LICENSE` and `LICENSES/`
- `THIRD_PARTY_NOTICES.md`
- `RC3_RUNTIME_AUDIT.md`
- `dependency-inventory.json`
- `native-component-inventory.json`
- `runtime-exclusions.json`
- `runtime-requirements.txt`
- original retained distribution license/notice files

These artifact-local records take precedence over summaries. See
`PACKAGING.md` for the clean-build and validation workflow.

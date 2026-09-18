# OneBoard Live Translate third-party notices

OneBoard Live Translate is a minimal fork of
[TheDeathDragon/LiveTranslate](https://github.com/TheDeathDragon/LiveTranslate).
The OneBoard work is distributed under [`GPL-3.0-only`](LICENSE). The upstream
LiveTranslate MIT notice is preserved in
[`LICENSES/LiveTranslate-MIT.txt`](LICENSES/LiveTranslate-MIT.txt), and the
vendored FunASR Python source notice is preserved in
[`LICENSES/FunASR-MIT.txt`](LICENSES/FunASR-MIT.txt).

The Windows package also contains separately licensed third-party software.
Each component remains the property of its copyright holder. Product names are
used only for identification and do not imply endorsement. This inventory is
not legal advice or a claim of patent, codec, model, export-control or commercial
clearance.

## RC3 package policy and artifact-local records

The `0.2.0-rc3` builder inventories the exact distributions that remain after
pruning and fails if any one lacks an installed or pinned supplemental license
file. Every package contains:

- `LICENSE` (OneBoard GPL-3.0-only);
- the complete tracked `LICENSES/` set listed below;
- this notice and `RC3_RUNTIME_AUDIT.md`;
- `runtime/LICENSE.txt` for CPython;
- each retained wheel's original license/notice files;
- `runtime-requirements.txt` and `dependency-inventory.json` for Python
  distributions;
- `native-component-inventory.json` for significant DLL/static components; and
- `runtime-exclusions.json`, recording reviewed removals and their rationale.

Package metadata can be incomplete and does not by itself establish compliance.
The inventories name exact files and provenance; the corresponding texts remain
the controlling records.

## RC2 blocker disposition in RC3

| Area | RC3 disposition |
| --- | --- |
| PyAV / FFmpeg / x264 / x265 | Removed. OneBoard supplies decoded NumPy arrays to faster-whisper. A hash-gated staged lazy import permits faster-whisper to import without PyAV; standalone media-file decoding is not a supported portable-package feature. No PyAV or FFmpeg/codec DLL is shipped. |
| Qt Multimedia / Qt FFmpeg | Removed. Source and packaged-window smoke require only QtCore, QtGui and QtWidgets. Qt Multimedia bindings, DLLs, plugins, QML and FFmpeg backend are excluded. |
| cuDNN / CUDA runtime | Removed from the CPU package. The unnecessary `cudnn64_9.dll` copied by the upstream CTranslate2 wheel is excluded, and the builder rejects known NVIDIA runtime DLLs. |
| CTranslate2 / Intel OpenMP | Retained for Whisper CPU inference with exact MIT, oneDNN, Intel EULA/OpenMP third-party and compiled-header notices. `libiomp5md.dll` is hash-pinned to the official Intel OpenMP 2025.3.0 Windows wheel. |
| Nine missing Python licenses | Resolved with exact version/source/ref/license records and tracked full texts; see the next table. |
| Unnecessary bulk | Tests, fixtures, caches, sample datasets, pip/ensurepip, debug/Tk helpers, native build files and unused Qt modules/plugins are removed by the builder without removing license subtrees. |

## Supplemental Python distribution records

These exact installed releases omitted a discoverable license file from their
wheel/sdist. RC3 supplies the authoritative upstream text and pins provenance:

| Distribution | Version | License | Authoritative source/ref | Packaged text |
| --- | ---: | --- | --- | --- |
| `antlr4-python3-runtime` | 4.9.3 | BSD-3-Clause | `antlr/antlr4`, tag `4.9.3`, commit `e4c1a74c66bd5290364ea2b36c97cd724b247357` | `LICENSES/ANTLR4-BSD-3-Clause.txt` |
| `ctranslate2` | 4.8.2 | MIT | `OpenNMT/CTranslate2`, tag `v4.8.2`, commit `d44d2d069eb88c7b7804da864c10c201501cb4a9` | `LICENSES/CTranslate2-MIT.txt` plus the CTranslate2/oneDNN/Intel notice set |
| `flatbuffers` | 25.12.19 | Apache-2.0 | `google/flatbuffers`, tag `v25.12.19`, commit `7e163021e59cca4f8e1e35a7c828b5c6b7915953` | `LICENSES/Apache-2.0.txt` |
| `jamo` | 0.4.1 | Apache-2.0 | `JDongian/python-jamo`, tag `v0.4.1`, commit `d087a9f5f52f066fb933ad1da8e9915703374c9a` | `LICENSES/Jamo-Apache-2.0.txt` |
| `jieba` | 0.42.1 | MIT | `fxsjy/jieba`, tag `v0.42.1`, commit `1e20c89b66f56c9301b0feed211733ffaa1bd72a` | `LICENSES/Jieba-MIT.txt` |
| `loguru` | 0.7.3 | MIT | `Delgan/loguru`, tag `0.7.3`, commit `ae3bfd1b85b6b4a3db535f69b975687c79498be4` | `LICENSES/Loguru-MIT.txt` |
| `sentencepiece` | 0.2.2 | Apache-2.0 | `google/sentencepiece`, tag `v0.2.2`, commit `e0cce7d37b065b5140349dbe12c6bcf6192fdd78` | `LICENSES/Apache-2.0.txt` |
| `tokenizers` | 0.23.2 | Apache-2.0 | `huggingface/tokenizers`, tag `v0.23.2`, commit `88a4498ad4ea1a9487b0a9b0ff881383fd5a06a3` | `LICENSES/Apache-2.0.txt`; the wheel's CycloneDX SBOM is also retained |
| `torch-complex` | 0.4.4 | Apache-2.0 | `kamo-naoyuki/pytorch_complex`, tag `v0.4.4`, commit `8a2ad1e47f3df25a30eb426f6ad781b89103fab3`; tagged package metadata declares Apache Software License although the repository omits a license file | `LICENSES/Apache-2.0.txt` |

The torch-complex record states the exact upstream evidence and omission; it does
not invent a copyright holder or a more specific license claim.

## CTranslate2 native stack

CTranslate2 `4.8.2` is required by faster-whisper. Its MIT text is in
`LICENSES/CTranslate2-MIT.txt`. The official Windows build recipe at the pinned
tag builds oneDNN `3.1.1` statically and uses Intel OpenMP `2025.3.0` dynamically.
It also builds dynamically loaded CUDA support into the monolithic DLL. RC3
cannot split that code safely, but it removes the separately copied cuDNN DLL,
ships no CUDA runtime, advertises only CPU support, and validates CPU compute
types.

The reviewed stack is documented by:

- `LICENSES/CTranslate2-Third-Party-Notices.txt` (cpu_features, spdlog/{fmt},
  vendored CPU headers, CUTLASS and CCCL/Thrust/CUB/libcudacxx at the exact
  CTranslate2 submodule commits);
- `LICENSES/oneDNN-Apache-2.0.txt` and
  `LICENSES/oneDNN-Third-Party-Programs.txt` for oneDNN tag `v3.1.1`, commit
  `64f6bcbcbab628e96f33a62c3e975f8535a7bde4`;
- `LICENSES/Intel-oneAPI-EULA.txt` and
  `LICENSES/Intel-OpenMP-Third-Party-Programs.txt`, copied from the official
  `intel-openmp==2025.3.0` Windows wheel whose `libiomp5md.dll` is byte-identical
  to the CTranslate2 wheel file (SHA-256
  `982233366b0afcda1e0f55a0b134097e35b779613f54ddb69e685e6cd06b755f`).

Intel's terms apply separately to that Redistributable. The publisher must keep
the required customer-license language and notices; this record does not provide
legal advice about a particular distribution arrangement.

## PyQt6 and Qt 6.11.2

PyQt6 `6.11.0` is retained under its public wheel's `GPL-3.0-only` terms,
consistent with the project's chosen GPL-3.0-only distribution. Qt is kept as
replaceable shared libraries under the PyQt6-Qt6 `6.11.2` wheel's LGPLv3 terms.
The package preserves both original wheel license files and adds the exact
QtBase LGPL text.

The retained Qt surface is limited to:

- `Qt6Core.dll`, `Qt6Gui.dll`, `Qt6Widgets.dll` and matching PyQt bindings;
- `qwindows`, `qminimal` and `qoffscreen` platform plugins;
- `qmodernwindowsstyle`; and
- `qgif`, `qico` and `qjpeg` image plugins.

`LICENSES/Qt-6.11.2-Third-Party-Notices.txt` reproduces only the applicable
Windows QtCore/QtGui/QtWidgets/qwindows/qjpeg attribution metadata and full
license texts from QtBase tag `v6.11.2` (tag object
`7a59d906fb765eb85759d4d3cae45d3f295f6359`, commit
`ef55f427f2c8b410d34f8a7681020a3000cf6866`). Qt Multimedia, Qt FFmpeg,
QML/Quick, WebEngine, SVG/PDF and `opengl32sw.dll` are not shipped, so their
module/backend notices are not used to conceal uncertainty.

Recipients can replace the Qt shared libraries in the runtime directory. The
publisher must provide the exact corresponding source/relinking information with
any public binary release and must not add restrictions that defeat applicable
GPL/LGPL rights.

## Vendored FunASR source provenance

All five files under `funasr_nano/` originate from `modelscope/FunASR` commit
`335eb1ea6156bc353283e21ae121a2224aa79175`. At inherited LiveTranslate import
commit `b549e858e37d684e3ca48f247901e439c580c3bb`, every file was byte-identical.
Four remain byte-identical; `funasr_nano/model.py` has only the documented model
loading change from inherited commit `d536d55c71d040d654292cae8c716266d71c6779`.

| Vendored path | Pinned source path |
| --- | --- |
| `funasr_nano/__init__.py` | `funasr/models/fun_asr_nano/__init__.py` |
| `funasr_nano/ctc.py` | `funasr/models/fun_asr_nano/ctc.py` |
| `funasr_nano/model.py` | `funasr/models/fun_asr_nano/model.py` |
| `funasr_nano/tools/__init__.py` | `funasr/models/fun_asr_nano/tools/__init__.py` |
| `funasr_nano/tools/utils.py` | `funasr/models/fun_asr_nano/tools/utils.py` |

The pinned directory has no nested license; the repository-root MIT license,
`Copyright (c) 2025 FunASR`, is reproduced in `LICENSES/FunASR-MIT.txt`.

## Models and external services

The base package contains no downloaded Whisper, SenseVoice, FunASR,
Anime-Whisper, Qwen or Ollama model cache (`models_bundled: false`). Downloads
require explicit user action and remain in the user's data directory. Models,
remote APIs and Ollama retain their own terms. Separate download does not prove
that every intended use is permitted; review the exact immutable model revision,
model card, nested weights and provider terms before redistribution or a
commercial deployment.

The included Silero VAD wheel asset and all other retained Python/native package
licenses are recorded in the generated inventories and original distribution
notice files. Microsoft runtime files retain their applicable redistribution
terms. A future GPU artifact requires a new binary and license audit.

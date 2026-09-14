# OneBoard Live Translate third-party notices

OneBoard Live Translate is a minimal fork of
[TheDeathDragon/LiveTranslate](https://github.com/TheDeathDragon/LiveTranslate).
OneBoard Live Translate is distributed as free and open-source software under
[`GPL-3.0-only`](LICENSE). The exact upstream LiveTranslate MIT license and
copyright notice are preserved separately in
[`LICENSES/LiveTranslate-MIT.txt`](LICENSES/LiveTranslate-MIT.txt).
The MIT license covering the vendored FunASR Python sources is preserved in
[`LICENSES/FunASR-MIT.txt`](LICENSES/FunASR-MIT.txt).

The Windows package also contains third-party software. Each component remains
the property of its respective copyright holder and is provided under its own
license. Product names are used only to identify those components and do not
imply endorsement.

This document is an inventory aid, not legal advice or a statement of commercial
clearance. The release publisher must review the exact artifact and satisfy all
applicable license terms before distribution.

**Project-license decision recorded on 2026-09-11:** release OneBoard Live
Translate under `GPL-3.0-only` and retain PyQt6. The public PyQt6 wheel's
`GPL-3.0-only` terms are compatible with that chosen strategy, so PyQt6 is no
longer a separate release blocker; a PySide6 migration and a commercial PyQt
license are not required for this strategy. This does not clear the exact native
libraries, PyAV/FFmpeg codecs, downloaded FunASR/SenseVoice model weights, other
model licenses, or any future GPU bundle. Those artifact-level release gates
remain open.

## Exact records in each Windows package

The repository uses open dependency ranges, so versions and transitive
dependencies may change between builds. The builder removes known test-only
packages and package test trees, but this is not a fully locked dependency set.
Each Windows package therefore includes:

- `LICENSE`, containing the OneBoard `GPL-3.0-only` license text;
- `LICENSES/LiveTranslate-MIT.txt`, preserving the exact upstream LiveTranslate
  MIT license and copyright notice;
- `LICENSES/FunASR-MIT.txt`, preserving the complete MIT license and copyright
  notice for the vendored FunASR Python sources;
- `THIRD_PARTY_NOTICES.md`, containing this release-publisher inventory;
- `runtime-requirements.txt`, listing every Python distribution copied into that
  particular build;
- `dependency-inventory.json`, containing the available package license metadata
  and paths to installed license/notice files;
- the original license and notice files under
  `runtime/Lib/site-packages/*-info/`; and
- `runtime/LICENSE.txt`, covering the bundled CPython runtime.

Those artifact-local files take precedence over this summary. Package metadata
can be blank, inaccurate, or limited to a Python wrapper while a wheel contains
additional native libraries. A package inventory is therefore not, by itself, a
license-compliance determination.

## Vendored FunASR source provenance

All five files under `funasr_nano/` originate from the authoritative
[`modelscope/FunASR`](https://github.com/modelscope/FunASR) repository at commit
[`335eb1ea6156bc353283e21ae121a2224aa79175`](https://github.com/modelscope/FunASR/commit/335eb1ea6156bc353283e21ae121a2224aa79175).
At the inherited LiveTranslate import commit
`b549e858e37d684e3ca48f247901e439c580c3bb`, every local file was
byte-identical to the corresponding file at that pinned FunASR revision.

| Vendored path | Authoritative source path | Current status against the pinned revision |
| --- | --- | --- |
| `funasr_nano/__init__.py` | `funasr/models/fun_asr_nano/__init__.py` | Byte-identical |
| `funasr_nano/ctc.py` | `funasr/models/fun_asr_nano/ctc.py` | Byte-identical |
| `funasr_nano/model.py` | `funasr/models/fun_asr_nano/model.py` | Modified after import |
| `funasr_nano/tools/__init__.py` | `funasr/models/fun_asr_nano/tools/__init__.py` | Byte-identical |
| `funasr_nano/tools/utils.py` | `funasr/models/fun_asr_nano/tools/utils.py` | Byte-identical |

The only post-import source change is inherited LiveTranslate commit
`d536d55c71d040d654292cae8c716266d71c6779`, which changes `model.py` to load
the causal language model with `from_pretrained(..., low_cpu_mem_usage=True)`
instead of constructing it from `AutoConfig`. The pinned core source directory
has no nested license or notice; the FunASR repository root applies the MIT
license and `Copyright (c) 2025 FunASR`, reproduced in full in
`LICENSES/FunASR-MIT.txt`.

This finding covers only the vendored Python source. Downloaded FunASR model
weights and derivatives remain governed by their own repository terms and the
separate FunASR model agreement; their release review remains open.

## Components needing release-publisher attention

| Component | How it is used | Published license information |
| --- | --- | --- |
| PyQt6 | Bundled Python UI bindings | Riverbank publishes PyQt6 under GNU GPL v3 or a Riverbank commercial license. The public wheel used by the current build reports `GPL-3.0-only`; PyQt is not LGPL. See [PyQt licensing](https://www.riverbankcomputing.com/software/pyqt/) and the artifact's PyQt6 license file. |
| Qt 6 | Shared Qt libraries bundled by the PyQt6 wheel | The wheel currently reports LGPL v3. Qt also contains separately licensed third-party code, and some Qt modules have different licensing choices. See [Qt licensing](https://doc.qt.io/qt-6/licensing.html), [Qt third-party code](https://doc.qt.io/qt-6/licenses-used-in-qt.html), and the artifact's Qt license file. |
| CPython 3.12 | Bundled interpreter and standard library | Python Software Foundation License Version 2 and other historical notices in `runtime/LICENSE.txt`. See [Python 3.12 licensing](https://docs.python.org/3.12/license.html). |
| PyAV and FFmpeg libraries | A transitive audio/media dependency copied from the build environment | PyAV source is BSD-3-Clause, while its binary wheel bundles FFmpeg and codec libraries with separate terms. Review the exact DLL set and build configuration. See [PyAV](https://github.com/PyAV-Org/PyAV) and [PyAV FFmpeg builds](https://github.com/PyAV-Org/pyav-ffmpeg). |
| `funasr_nano/*.py` | Vendored Fun-ASR-Nano implementation copied into every package | Provenance is verified against FunASR commit `335eb1ea6156bc353283e21ae121a2224aa79175`: four files remain byte-identical and `model.py` contains the documented inherited loading change. The applicable root license is MIT, `Copyright (c) 2025 FunASR`; the complete notice is shipped as `LICENSES/FunASR-MIT.txt`. This source finding does not clear downloaded model weights. |
| soxr | Transitive resampling library | The current package metadata reports `LGPL-2.1-or-later`; see its installed license files. |
| yasbd-lib | Sentence-boundary library | The current package metadata reports `MPL-2.0`; see its installed license file. |
| PyTorch, CTranslate2, NumPy, SciPy, libsndfile, and other native wheels | Bundled ASR, numerical, and audio runtime | These packages contain or link additional native components. Their complete license files and notices remain in the artifact. Review the exact versions and binaries, rather than relying only on the top-level package label. |
| Microsoft runtime DLLs | Runtime DLLs copied with CPython and Qt | Review the Microsoft redistribution terms that apply to the exact files in the release artifact. |

Other required and transitive Python packages are predominantly published under
MIT, BSD, Apache-2.0, ISC, MPL-2.0, or similarly identified terms. The complete
set is build-dependent and is recorded in the two artifact inventories described
above. Do not infer that an omitted package is absent from a particular build.

## Models and external runtimes

The base OneBoard Windows ZIP/installer does not contain downloaded Whisper,
SenseVoice, FunASR, Anime-Whisper, or Qwen model caches. Model downloads require
an explicit user action and are stored in the user's data directory. Model
weights are licensed separately from the application and from the inference
software.

| Component | Packaging status | License information observed during this review |
| --- | --- | --- |
| Silero VAD | Its small VAD asset is included in the `silero-vad` Python wheel | The project and current wheel identify the VAD package/model as MIT. See [Silero VAD](https://github.com/snakers4/silero-vad) and its artifact license file. |
| `Systran/faster-whisper-small` | Default ASR model; downloaded separately and not pinned to a repository revision | The current Hugging Face model card identifies the converted checkpoint as MIT. See [faster-whisper-small](https://huggingface.co/Systran/faster-whisper-small). Recheck and retain the exact license at download/release time. |
| `qwen3:4b-instruct-2507-q4_K_M` | Default translation model; downloaded by the user's Ollama service, not bundled | The current Ollama tag (displayed digest prefix `0edcdef34593`) embeds Apache License 2.0. See the [exact Ollama model tag](https://ollama.com/library/qwen3:4b-instruct-2507-q4_K_M) and the [upstream Qwen checkpoint](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507). Recheck the tag/digest and license before any publisher-hosted redistribution. |
| SenseVoice Small | Optional Advanced model; downloaded separately | The available hubs do not present one consistent label: the current Hugging Face page uses `model-license`, while the ModelScope page has displayed Apache-2.0. The FunASR project separately publishes a FunASR Model Open Source License Agreement. Preserve the exact downloaded license and obtain manual review before commercial use or redistribution. |
| Fun-ASR-Nano / Fun-ASR-MLT-Nano | Optional Advanced models; downloaded separately and may include Qwen3-0.6B weights | Current hub pages have displayed Apache-2.0, while the FunASR repository also publishes a separate model agreement. Verify every downloaded repository, nested weight, revision, and attribution requirement before use or redistribution. See the [FunASR model agreement](https://github.com/modelscope/FunASR/blob/main/MODEL_LICENSE). |
| `litagin/anime-whisper` | Optional Advanced model; downloaded separately | The current model card identifies it as MIT. Its base-model and training-data provenance should still be reviewed for the intended release/use. See [Anime-Whisper](https://huggingface.co/litagin/anime-whisper). |
| Ollama | Managed prerequisite installed separately by the user; it is not in the OneBoard package | The Ollama source repository currently uses MIT. Models served by Ollama retain their own licenses. See [Ollama's license](https://github.com/ollama/ollama/blob/main/LICENSE). |
| NVIDIA/CUDA components | Not included in the current CPU Windows package | A future GPU build requires a new component inventory and review of the exact NVIDIA/CUDA/cuDNN redistribution terms. |

Remote APIs and user-selected models exposed through Advanced settings are not
distributed by OneBoard. Their provider terms and model licenses apply separately.

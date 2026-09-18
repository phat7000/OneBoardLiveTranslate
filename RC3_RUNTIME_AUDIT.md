# OneBoard Live Translate RC3 runtime reachability audit

Audit date: 2026-09-18

Target: `0.2.0-rc3`, Windows x64 CPU portable ZIP

This audit is based on source imports, dynamic import sites, the installed wheel
contents, upstream build recipes, and packaged-process smoke behavior. Pip
dependency metadata was evidence, not the decision rule.

## REQUIRED

| Component | Runtime reason | RC3 action |
| --- | --- | --- |
| CPython 3.12 | Application interpreter and multiprocessing spawn runtime | Retain interpreter, standard library and required extension DLLs; remove tests, Tk, debug and test helpers, `ensurepip` and `pip`. |
| PyQt6; QtCore, QtGui and QtWidgets | Both OneBoard windows, Advanced Control Panel, dialogs, tray, subtitles and transcript widgets | Retain only the three bindings and their Windows platform/style/basic image plugins. |
| PyTorch CPU and torchaudio CPU | Silero VAD, FunASR, tensor operations and resampling; `torch` imports its public `torch.testing` helpers from `autograd.gradcheck` during normal initialization | Retain runtime code/DLLs and `torch.testing`; remove headers, link libraries, CMake/share and developer executables. |
| faster-whisper and CTranslate2 | Supported Whisper ASR engine | Retain CTranslate2 CPU operation, oneDNN and Intel OpenMP. |
| Silero VAD | Default voice activity detection | Retain its package and small packaged asset. |
| FunASR/SenseVoice stack | Supported Advanced ASR engines | Retain FunASR, ModelScope, ONNX Runtime, Transformers, SentencePiece, Tokenizers and their runtime dependencies. |
| Numba and LLVM/llvmlite | Reachable through the supported FunASR/librosa audio paths | Retain. Removing them breaks reachable model/audio preprocessing. |
| PyAudioWPatch and audio/numerical dependencies | Microphone and Windows loopback capture plus signal processing | Retain. |
| Translation clients and `yasbd-lib` | Local/remote translation and sentence segmentation | Retain. |

## OPTIONAL BUT SUPPORTED

Models, Ollama, microphone/loopback devices, remote translation services and
remote ASR are selected or installed by the user. Their client code remains in
the package, but model weights, Ollama, GPU drivers and service binaries remain
unbundled. Advanced continues to expose upstream languages and engines.

CTranslate2's official Windows `4.8.2` wheel contains one monolithic DLL built
with CPU and dynamically loaded CUDA backends. The GPU portions cannot be split
from that DLL without rebuilding upstream. RC3 retains the reviewed DLL because
the CPU Whisper path requires it, removes the separately copied cuDNN DLL, ships
no CUDA runtime DLL, describes the artifact only as CPU portable, and exercises
only the CPU backend.

## UNUSED IN THE SUPPORTED PORTABLE FLOW

| Component | Evidence | RC3 action |
| --- | --- | --- |
| PyAV | OneBoard capture and both local Whisper call sites pass `float32` NumPy arrays. faster-whisper calls `decode_audio` only for a path/file input. | Exclude `av`, `av.libs` and metadata. Apply a hash-gated staged lazy import so importing faster-whisper does not import PyAV. Standalone faster-whisper file decoding is explicitly outside the supported OneBoard package. |
| PyAV's FFmpeg/x264/x265/etc. DLLs | Present only inside the removed PyAV wheel payload. | Exclude completely. |
| Qt Multimedia and its FFmpeg/Windows backends | No application source imports `PyQt6.QtMultimedia`, Qt Multimedia, QAudio or QMedia APIs. | Exclude bindings, Qt DLLs, plugins, QML and Qt FFmpeg DLLs. |
| cuDNN and CUDA runtime DLLs | CPU CTranslate2 imports and CPU compute types work without the wheel's unused `cudnn64_9.dll`; PyTorch is a `+cpu` build. | Exclude cuDNN and fail the build if any known NVIDIA runtime DLL appears. |
| ONNX sample datasets | Not imported by application/model runtime. | Exclude `onnxruntime/datasets`. |
| `pip` and `ensurepip` | Customer runtime performs no package installation. | Exclude. |
| CPython debug/test/Tk helpers | No supported flow imports them; release uses non-debug CPython and PyQt. | Exclude `_d` binaries, `_test*`, `_ctypes_test`, Tk and related payload. |
| Package tests, examples and native development files | No supported runtime dependency. | Exclude generic test/fixture trees, PyQt binding sources/tools, PyTorch headers/link libraries/CMake/share/tests/bin and Python caches. License/notice subtrees are always preserved. |
| Unused Qt modules/plugins | Static source scan uses only QtCore/QtGui/QtWidgets; the packaged window smoke covers the retained set. | Allowlist exact bindings, DLLs and plugins; fail on drift. |

## Automated enforcement

`packaging/build_oneboard.py` performs every exclusion before smoke testing and
then enforces a closed allowlist for Qt plus forbidden binary/path checks. It
hash-gates the faster-whisper patch and Intel OpenMP DLL, inventories only the
distributions actually left in the stage, rejects a distribution without an
auditable license file, and records significant native components separately.

The packaged smoke launches the real EXE with isolated search paths and a fresh
profile. It verifies application imports, PyAV/QtMultimedia absence, Qt
initialization, the primary window, Display Window, Advanced Control Panel,
torchaudio resampling, Silero VAD construction, CTranslate2 CPU compute types,
and a spawned ASR worker using the bundled interpreter.

This is a technical reachability and packaging record, not legal advice or a
claim of codec, patent, model, export-control or commercial-use clearance.

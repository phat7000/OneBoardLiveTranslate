"""Build a relocatable Windows distribution using a prepared developer venv.

This deliberately reuses upstream's ordinary Python modules and full dependency
environment instead of freezing dynamic ASR/model imports into one executable.
No installer, package manager, or model download runs on the customer's machine.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import sysconfig
import uuid
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from branding import APP_NAME, APP_SHORT_NAME, COMPANY_NAME


DEVELOPMENT_DISTRIBUTIONS = {"iniconfig", "pluggy", "pytest"}
EXCLUDED_RUNTIME_DISTRIBUTIONS = DEVELOPMENT_DISTRIBUTIONS | {"av", "pip"}
REVOKED_RELEASE_VERSIONS = {"0.2.0-rc1", "0.2.0-rc2"}
NON_RUNTIME_TREE_NAMES = {
    "__pycache__",
    "_tests",
    "fixtures",
    "selftest",
    "test",
    "testdata",
    "tests",
}
NOTICE_TREE_NAMES = {"licence", "licences", "license", "licenses", "notices"}
NON_RUNTIME_PACKAGE_FILES = {("transformers", "testing_utils.py")}
RELEASE_NOTICE_FILES = (
    Path("LICENSE"),
    Path("LICENSES") / "ANTLR4-BSD-3-Clause.txt",
    Path("LICENSES") / "Apache-2.0.txt",
    Path("LICENSES") / "CTranslate2-MIT.txt",
    Path("LICENSES") / "CTranslate2-Third-Party-Notices.txt",
    Path("LICENSES") / "FunASR-MIT.txt",
    Path("LICENSES") / "Intel-oneAPI-EULA.txt",
    Path("LICENSES") / "Intel-OpenMP-Third-Party-Programs.txt",
    Path("LICENSES") / "Jamo-Apache-2.0.txt",
    Path("LICENSES") / "Jieba-MIT.txt",
    Path("LICENSES") / "LiveTranslate-MIT.txt",
    Path("LICENSES") / "Loguru-MIT.txt",
    Path("LICENSES") / "oneDNN-Apache-2.0.txt",
    Path("LICENSES") / "oneDNN-Third-Party-Programs.txt",
    Path("LICENSES") / "Qt-6.11.2-LGPL-3.0.txt",
    Path("LICENSES") / "Qt-6.11.2-Third-Party-Notices.txt",
    Path("RC3_RUNTIME_AUDIT.md"),
    Path("THIRD_PARTY_NOTICES.md"),
)

SUPPLEMENTAL_LICENSE_RECORDS = {
    "antlr4-python3-runtime": {
        "version": "4.9.3",
        "license_expression": "BSD-3-Clause",
        "license_files": ["LICENSES/ANTLR4-BSD-3-Clause.txt"],
        "source": "https://github.com/antlr/antlr4",
        "source_ref": "4.9.3 (e4c1a74c66bd5290364ea2b36c97cd724b247357)",
    },
    "ctranslate2": {
        "version": "4.8.2",
        "license_expression": "MIT",
        "license_files": [
            "LICENSES/Apache-2.0.txt",
            "LICENSES/CTranslate2-MIT.txt",
            "LICENSES/CTranslate2-Third-Party-Notices.txt",
            "LICENSES/Intel-oneAPI-EULA.txt",
            "LICENSES/Intel-OpenMP-Third-Party-Programs.txt",
            "LICENSES/oneDNN-Apache-2.0.txt",
            "LICENSES/oneDNN-Third-Party-Programs.txt",
        ],
        "source": "https://github.com/OpenNMT/CTranslate2",
        "source_ref": "v4.8.2 (d44d2d069eb88c7b7804da864c10c201501cb4a9)",
    },
    "flatbuffers": {
        "version": "25.12.19",
        "license_expression": "Apache-2.0",
        "license_files": ["LICENSES/Apache-2.0.txt"],
        "source": "https://github.com/google/flatbuffers",
        "source_ref": "v25.12.19 (7e163021e59cca4f8e1e35a7c828b5c6b7915953)",
    },
    "jamo": {
        "version": "0.4.1",
        "license_expression": "Apache-2.0",
        "license_files": ["LICENSES/Jamo-Apache-2.0.txt"],
        "source": "https://github.com/JDongian/python-jamo",
        "source_ref": "v0.4.1 (d087a9f5f52f066fb933ad1da8e9915703374c9a)",
    },
    "jieba": {
        "version": "0.42.1",
        "license_expression": "MIT",
        "license_files": ["LICENSES/Jieba-MIT.txt"],
        "source": "https://github.com/fxsjy/jieba",
        "source_ref": "v0.42.1 (1e20c89b66f56c9301b0feed211733ffaa1bd72a)",
    },
    "loguru": {
        "version": "0.7.3",
        "license_expression": "MIT",
        "license_files": ["LICENSES/Loguru-MIT.txt"],
        "source": "https://github.com/Delgan/loguru",
        "source_ref": "0.7.3 (ae3bfd1b85b6b4a3db535f69b975687c79498be4)",
    },
    "sentencepiece": {
        "version": "0.2.2",
        "license_expression": "Apache-2.0",
        "license_files": ["LICENSES/Apache-2.0.txt"],
        "source": "https://github.com/google/sentencepiece",
        "source_ref": "v0.2.2 (e0cce7d37b065b5140349dbe12c6bcf6192fdd78)",
    },
    "tokenizers": {
        "version": "0.23.2",
        "license_expression": "Apache-2.0",
        "license_files": ["LICENSES/Apache-2.0.txt"],
        "source": "https://github.com/huggingface/tokenizers",
        "source_ref": "v0.23.2 (88a4498ad4ea1a9487b0a9b0ff881383fd5a06a3)",
    },
    "torch-complex": {
        "version": "0.4.4",
        "license_expression": "Apache-2.0",
        "license_files": ["LICENSES/Apache-2.0.txt"],
        "source": "https://github.com/kamo-naoyuki/pytorch_complex",
        "source_ref": "v0.4.4 (8a2ad1e47f3df25a30eb426f6ad781b89103fab3); upstream package metadata declares Apache Software License",
    },
}

FASTER_WHISPER_AUDIO_SHA256 = (
    "60a1d8638f718cbf6d245aed3e5a5aa61c1f822a0b0fe9b48a7c928d47c23909"
)
INTEL_OPENMP_SHA256 = (
    "982233366b0afcda1e0f55a0b134097e35b779613f54ddb69e685e6cd06b755f"
)
QT_BINDINGS = {"QtCore.pyd", "QtGui.pyd", "QtWidgets.pyd", "sip.cp312-win_amd64.pyd"}
QT_DLLS = {
    "concrt140.dll",
    "d3dcompiler_47.dll",
    "msvcp140.dll",
    "msvcp140_1.dll",
    "msvcp140_2.dll",
    "msvcp140_atomic_wait.dll",
    "msvcp140_codecvt_ids.dll",
    "Qt6Core.dll",
    "Qt6Gui.dll",
    "Qt6Widgets.dll",
    "vccorlib140.dll",
    "vcruntime140.dll",
    "vcruntime140_1.dll",
    "vcruntime140_threads.dll",
}
QT_PLUGINS = {
    "imageformats/qgif.dll",
    "imageformats/qico.dll",
    "imageformats/qjpeg.dll",
    "platforms/qminimal.dll",
    "platforms/qoffscreen.dll",
    "platforms/qwindows.dll",
    "styles/qmodernwindowsstyle.dll",
}


def canonical_distribution_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def excluded_runtime_entry(name: str) -> bool:
    """Match only package roots or metadata for explicitly excluded projects."""
    lowered = name.lower()
    root_names = {"_pytest", "av", "av.libs", "pip"}
    root_names.update(EXCLUDED_RUNTIME_DISTRIBUTIONS)
    root_names.update(name.replace("-", "_") for name in EXCLUDED_RUNTIME_DISTRIBUTIONS)
    if lowered in root_names:
        return True
    for distribution_name in EXCLUDED_RUNTIME_DISTRIBUTIONS:
        variants = {
            distribution_name,
            distribution_name.replace("-", "_"),
            distribution_name.replace("-", "."),
        }
        if any(
            lowered.startswith(variant + "-")
            and lowered.endswith((".dist-info", ".egg-info"))
            for variant in variants
        ):
            return True
    return False


def validate_artifact_version(
    version: str, *, skip_archive: bool, iscc: str | None
) -> None:
    """Never recreate a revoked ZIP or installer version."""
    if version in REVOKED_RELEASE_VERSIONS and (not skip_archive or iscc):
        raise RuntimeError(
            f"Release version {version} is revoked; assign and commit a new "
            "approved version before building a ZIP or installer"
        )


def run(command: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(command, check=True, text=True, **kwargs)


def application_file(relative: Path) -> bool:
    """Only application modules/assets, never bootstrap/updater/developer state."""
    if relative.name.startswith("test_") or any(
        part.lower() in NON_RUNTIME_TREE_NAMES for part in relative.parts[:-1]
    ):
        return False
    if len(relative.parts) == 1:
        return relative.suffix == ".py" or relative.name == "config.yaml"
    return relative.parts[0] in {"funasr_nano", "i18n"} and relative.suffix in {".py", ".json", ".yaml"}


def ignored_runtime_files(_directory: str, names: list[str]) -> set[str]:
    directory_name = Path(_directory).name.lower()
    in_notice_tree = any(
        part.lower() in NOTICE_TREE_NAMES for part in Path(_directory).parts
    )
    return {
        name for name in names
        if name in {".git", "direct_url.json"}
        or name.lower() == "__pycache__"
        or (not in_notice_tree and name.lower() in NON_RUNTIME_TREE_NAMES)
        or (directory_name, name.lower()) in NON_RUNTIME_PACKAGE_FILES
        or excluded_runtime_entry(name)
        or name.endswith((".pyc", ".pyo", ".pdb"))
        or bool(re.search(r"_d\.(?:dll|lib|pyd)$", name, re.IGNORECASE))
        or bool(re.fullmatch(r"_?test.*\.pyd", name, re.IGNORECASE))
        or name.lower() in {
            "_ctypes_test.pyd",
            "_tkinter.pyd",
            "py.ico",
            "pyc.ico",
            "pyd.ico",
            "python_lib.cat",
            "tcl86t.dll",
            "tk86t.dll",
        }
    }


def remove_stage(path: Path, output: Path) -> None:
    """Never recursively delete outside the explicitly scoped release output."""
    if path.resolve().parent != output.resolve() or not path.name.startswith(APP_SHORT_NAME):
        raise ValueError(f"Refusing to remove unexpected build path: {path}")
    if path.is_symlink():
        raise ValueError(f"Refusing to remove linked build path: {path}")
    if path.exists():
        shutil.rmtree(path)


def remove_stale_artifact(path: Path, output: Path, expected_names: set[str]) -> None:
    """Remove only an exact artifact name for this version before rebuilding."""
    if path.parent.resolve() != output.resolve() or path.name not in expected_names:
        raise ValueError(f"Refusing to remove unexpected release artifact: {path}")
    if path.exists() or path.is_symlink():
        if path.is_dir() and not path.is_symlink():
            raise ValueError(f"Refusing to unlink an artifact directory: {path}")
        path.unlink()


def copy_runtime(runtime: Path) -> None:
    base = Path(sys.base_prefix)
    site_packages = Path(sysconfig.get_paths()["purelib"])
    if sys.prefix == sys.base_prefix:
        raise RuntimeError("Build with a dedicated virtual environment, not a system Python")
    runtime.mkdir()
    for filename in ("python.exe", "pythonw.exe", "python3.dll", f"python{sys.version_info.major}{sys.version_info.minor}.dll", "vcruntime140.dll", "vcruntime140_1.dll", "LICENSE.txt"):
        source = base / filename
        if not source.is_file():
            raise RuntimeError(f"Required CPython runtime file is missing: {source}")
        shutil.copy2(source, runtime / filename)
    shutil.copytree(base / "DLLs", runtime / "DLLs", ignore=ignored_runtime_files)

    def ignore_standard(directory: str, names: list[str]) -> set[str]:
        ignored = ignored_runtime_files(directory, names)
        if Path(directory) == base / "Lib":
            ignored.update(
                {
                    "ensurepip",
                    "site-packages",
                    "test",
                    "idlelib",
                    "tkinter",
                    "turtledemo",
                }
                & set(names)
            )
        return ignored

    shutil.copytree(base / "Lib", runtime / "Lib", ignore=ignore_standard)
    shutil.copytree(site_packages, runtime / "Lib" / "site-packages", ignore=ignored_runtime_files)
    # Explicit isolated search paths prohibit registry/system-Python/user-site
    # fallback and remain valid after moving the extracted application folder.
    (runtime / f"python{sys.version_info.major}{sys.version_info.minor}._pth").write_text(
        ".\nDLLs\nLib\nLib/site-packages\n../app\nimport site\n", encoding="ascii"
    )


def remove_runtime_path(runtime: Path, relative: Path) -> None:
    """Remove one generated runtime path without allowing scope escape or links."""
    root = runtime.resolve()
    target = runtime / relative
    resolved = target.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ValueError(f"Refusing to prune outside runtime: {target}") from error
    if target.is_symlink():
        raise ValueError(f"Refusing to prune linked runtime path: {target}")
    if target.is_dir():
        shutil.rmtree(target)
    elif target.exists():
        target.unlink()


def patch_faster_whisper_audio(runtime: Path) -> None:
    """Make PyAV optional for OneBoard's NumPy-only faster-whisper input path."""
    audio = runtime / "Lib" / "site-packages" / "faster_whisper" / "audio.py"
    original = audio.read_bytes()
    actual_hash = hashlib.sha256(original).hexdigest()
    if actual_hash != FASTER_WHISPER_AUDIO_SHA256:
        raise RuntimeError(
            "Unsupported faster-whisper audio.py; review the lazy PyAV patch "
            f"before packaging (SHA256 {actual_hash})"
        )
    text = original.decode("utf-8")
    text = text.replace("import av\n", "", 1)
    marker = "\n\ndef decode_audio(\n"
    lazy_loader = '''\n\n_AV_IMPORT_ERROR = (\n    "This portable OneBoard build accepts decoded NumPy audio and does not "\n    "bundle PyAV/FFmpeg. File-path decoding is not part of the supported "\n    "OneBoard runtime flow."\n)\n\n\ndef _require_av():\n    try:\n        import av\n    except ImportError as error:\n        raise RuntimeError(_AV_IMPORT_ERROR) from error\n    return av\n\n\ndef decode_audio(\n'''
    if marker not in text:
        raise RuntimeError("faster-whisper lazy PyAV patch marker is missing")
    text = text.replace(marker, lazy_loader, 1)
    text = text.replace(
        '    resampler = av.audio.resampler.AudioResampler(\n',
        '    av = _require_av()\n    resampler = av.audio.resampler.AudioResampler(\n',
        1,
    )
    text = text.replace(
        "        except av.error.InvalidDataError:\n",
        "        except _require_av().error.InvalidDataError:\n",
        1,
    )
    text = text.replace(
        "    fifo = av.audio.fifo.AudioFifo()\n",
        "    fifo = _require_av().audio.fifo.AudioFifo()\n",
        1,
    )
    if "import av\n" in text.split("def _require_av", 1)[0]:
        raise RuntimeError("faster-whisper still imports PyAV eagerly")
    audio.write_text(text, encoding="utf-8", newline="\n")


def prune_runtime(runtime: Path) -> None:
    """Apply the reviewed RC3 CPU-runtime exclusions to every future build."""
    site_packages = runtime / "Lib" / "site-packages"
    patch_faster_whisper_audio(runtime)

    for name in ("av", "av.libs", "pip", "_pytest"):
        remove_runtime_path(runtime, Path("Lib/site-packages") / name)
    for path in site_packages.iterdir():
        if path.is_dir() and excluded_runtime_entry(path.name):
            remove_runtime_path(runtime, path.relative_to(runtime))

    for relative in (
        Path("Lib/ensurepip"),
        Path("Lib/site-packages/onnxruntime/datasets"),
        Path("Lib/site-packages/torch/bin"),
        Path("Lib/site-packages/torch/include"),
        Path("Lib/site-packages/torch/share"),
        Path("Lib/site-packages/PyQt6/bindings"),
        Path("Lib/site-packages/PyQt6/lupdate"),
        Path("Lib/site-packages/PyQt6/uic"),
    ):
        remove_runtime_path(runtime, relative)

    torch_lib = site_packages / "torch" / "lib"
    if torch_lib.is_dir():
        for pattern in ("*.exp", "*.lib"):
            for path in torch_lib.rglob(pattern):
                remove_runtime_path(runtime, path.relative_to(runtime))

    for path in runtime.rglob("*.pyd"):
        if re.fullmatch(r"_?test.*\.pyd", path.name, re.IGNORECASE) or path.name.lower() == "_ctypes_test.pyd":
            remove_runtime_path(runtime, path.relative_to(runtime))

    pyqt = site_packages / "PyQt6"
    for path in pyqt.iterdir():
        if path.is_file() and (
            (path.suffix.lower() == ".pyd" and path.name not in QT_BINDINGS)
            or path.suffix.lower() in {".pyi", ".sip"}
            or path.name == "py.typed"
        ):
            remove_runtime_path(runtime, path.relative_to(runtime))

    qt_root = pyqt / "Qt6"
    for directory in ("qml", "qsci", "translations"):
        remove_runtime_path(runtime, (qt_root / directory).relative_to(runtime))
    qt_bin = qt_root / "bin"
    for path in qt_bin.iterdir():
        if path.is_file() and path.name not in QT_DLLS:
            remove_runtime_path(runtime, path.relative_to(runtime))
    plugins = qt_root / "plugins"
    for path in sorted(plugins.rglob("*"), reverse=True):
        if path.is_file():
            relative_plugin = path.relative_to(plugins).as_posix()
            if relative_plugin not in QT_PLUGINS:
                remove_runtime_path(runtime, path.relative_to(runtime))
        elif path.is_dir() and not any(path.iterdir()):
            remove_runtime_path(runtime, path.relative_to(runtime))

    remove_runtime_path(
        runtime, Path("Lib/site-packages/ctranslate2/cudnn64_9.dll")
    )


def distribution_notice_files(files) -> list[str]:
    """Return meaningful license/notice paths, excluding generated caches."""
    notices = []
    for item in files or []:
        parts = tuple(part.lower() for part in item.parts)
        if "__pycache__" in parts or item.suffix.lower() in {".pyc", ".pyo"}:
            continue
        if any(
            "license" in part or "notice" in part or "copying" in part
            for part in parts
        ):
            notices.append(str(item))
    return notices


def verify_dependency_notice_inventory(stage: Path, records: list[dict]) -> None:
    """Require every inventoried dependency notice to exist in the stage."""
    site_packages = (stage / "runtime" / "Lib" / "site-packages").resolve()
    stage_root = stage.resolve()
    missing = []
    for record in records:
        for relative_name in record["license_files"]:
            candidate = (site_packages / Path(relative_name)).resolve()
            try:
                candidate.relative_to(site_packages)
            except ValueError:
                missing.append(f'{record["name"]}: {relative_name} (outside runtime)')
                continue
            if not candidate.is_file():
                missing.append(f'{record["name"]}: {relative_name}')
        for relative_name in record["supplemental_license_files"]:
            candidate = (stage / Path(relative_name)).resolve()
            try:
                candidate.relative_to(stage_root)
            except ValueError:
                missing.append(f'{record["name"]}: {relative_name} (outside stage)')
                continue
            if not candidate.is_file():
                missing.append(f'{record["name"]}: {relative_name}')
        if not record["license_files"] and not record["supplemental_license_files"]:
            missing.append(f'{record["name"]}: no auditable license file')
    if missing:
        raise RuntimeError(
            "Dependency inventory references missing license/notice files: "
            + ", ".join(missing[:10])
        )


def dependency_inventory(stage: Path) -> list[dict]:
    site_packages = stage / "runtime" / "Lib" / "site-packages"
    records = []
    distributions = importlib.metadata.distributions(path=[str(site_packages)])
    for distribution in sorted(
        distributions, key=lambda item: item.metadata["Name"].lower()
    ):
        metadata = distribution.metadata
        canonical_name = canonical_distribution_name(metadata["Name"])
        if canonical_name in EXCLUDED_RUNTIME_DISTRIBUTIONS:
            continue
        supplemental = SUPPLEMENTAL_LICENSE_RECORDS.get(canonical_name)
        if supplemental and distribution.version != supplemental["version"]:
            raise RuntimeError(
                f"Supplemental license record for {metadata['Name']} expects "
                f"{supplemental['version']}, not staged {distribution.version}"
            )
        record = {
            "name": metadata["Name"],
            "version": distribution.version,
            "license_expression": (
                supplemental["license_expression"]
                if supplemental
                else metadata.get("License-Expression")
            ),
            "license": metadata.get("License"),
            "license_classifiers": [item for item in metadata.get_all("Classifier", []) if item.startswith("License ::")],
            "license_files": distribution_notice_files(distribution.files),
            "supplemental_license_files": (
                supplemental["license_files"] if supplemental else []
            ),
            "authoritative_source": supplemental["source"] if supplemental else None,
            "source_ref": supplemental["source_ref"] if supplemental else None,
        }
        records.append(record)
    verify_dependency_notice_inventory(stage, records)
    (stage / "dependency-inventory.json").write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    (stage / "runtime-requirements.txt").write_text(
        "# Exact installed distributions copied by this build; model weights are separate.\n"
        + "\n".join(f'{record["name"]}=={record["version"]}' for record in records) + "\n",
        encoding="utf-8",
    )
    return records


def _file_record(stage: Path, relative: Path) -> dict:
    path = stage / relative
    if not path.is_file():
        raise RuntimeError(f"Required native runtime file is missing: {relative}")
    return {
        "path": relative.as_posix(),
        "size": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def native_component_inventory(stage: Path, dependencies: list[dict]) -> list[dict]:
    """Record exact significant native components and verify their notices."""
    versions = {
        canonical_distribution_name(record["name"]): record["version"]
        for record in dependencies
    }
    expected = {
        "ctranslate2": "4.8.2",
        "pyqt6": "6.11.0",
        "pyqt6-qt6": "6.11.2",
        "torch": "2.14.0+cpu",
    }
    drift = [
        f"{name}: expected {version}, staged {versions.get(name)!r}"
        for name, version in expected.items()
        if versions.get(name) != version
    ]
    if drift:
        raise RuntimeError("Unreviewed native dependency drift: " + "; ".join(drift))

    runtime_base = Path("runtime/Lib/site-packages")
    openmp = _file_record(
        stage, runtime_base / "ctranslate2" / "libiomp5md.dll"
    )
    if openmp["sha256"] != INTEL_OPENMP_SHA256:
        raise RuntimeError(
            "libiomp5md.dll does not match the reviewed Intel OpenMP 2025.3.0 "
            f"runtime ({openmp['sha256']})"
        )
    qt_root = stage / runtime_base / "PyQt6" / "Qt6"
    qt_files = [
        _file_record(stage, path.relative_to(stage))
        for path in sorted((qt_root / "bin").glob("Qt6*.dll"))
    ]
    qt_plugins = [
        _file_record(stage, path.relative_to(stage))
        for path in sorted((qt_root / "plugins").rglob("*.dll"))
    ]
    records = [
        {
            "name": "CTranslate2",
            "version": versions["ctranslate2"],
            "role": "required faster-whisper CPU inference engine; official wheel's monolithic DLL also contains dormant dynamically loaded CUDA support, but no CUDA runtime is bundled",
            "provenance": "OpenNMT/CTranslate2 v4.8.2 commit d44d2d069eb88c7b7804da864c10c201501cb4a9; official Windows wheel build recipe",
            "files": [
                _file_record(
                    stage, runtime_base / "ctranslate2" / "ctranslate2.dll"
                ),
                _file_record(
                    stage,
                    runtime_base
                    / "ctranslate2"
                    / "_ext.cp312-win_amd64.pyd",
                ),
            ],
            "license_files": [
                "LICENSES/Apache-2.0.txt",
                "LICENSES/CTranslate2-MIT.txt",
                "LICENSES/CTranslate2-Third-Party-Notices.txt",
            ],
        },
        {
            "name": "Intel OpenMP runtime",
            "version": "2025.3.0",
            "role": "required dynamic OpenMP runtime for the reviewed CTranslate2 CPU binary",
            "provenance": "byte-identical to intel-openmp 2025.3.0 official Windows wheel",
            "files": [openmp],
            "license_files": [
                "LICENSES/Intel-oneAPI-EULA.txt",
                "LICENSES/Intel-OpenMP-Third-Party-Programs.txt",
            ],
        },
        {
            "name": "oneDNN",
            "version": "3.1.1",
            "role": "statically linked CPU inference backend in CTranslate2",
            "provenance": "oneapi-src/oneDNN v3.1.1 commit 64f6bcbcbab628e96f33a62c3e975f8535a7bde4, pinned by the CTranslate2 v4.8.2 Windows build recipe",
            "files": [],
            "license_files": [
                "LICENSES/oneDNN-Apache-2.0.txt",
                "LICENSES/oneDNN-Third-Party-Programs.txt",
            ],
        },
        {
            "name": "PyQt6 and Qt",
            "version": f"PyQt6 {versions['pyqt6']}; Qt {versions['pyqt6-qt6']}",
            "role": "required QtCore/QtGui/QtWidgets UI and reviewed Windows plugins",
            "provenance": "Riverbank PyQt6 and PyQt6-Qt6 wheels; QtBase v6.11.2 commit ef55f427f2c8b410d34f8a7681020a3000cf6866",
            "files": qt_files + qt_plugins,
            "license_files": [
                "runtime/Lib/site-packages/pyqt6-6.11.0.dist-info/licenses/LICENSE",
                "runtime/Lib/site-packages/pyqt6_qt6-6.11.2.dist-info/LICENSE",
                "LICENSES/Qt-6.11.2-LGPL-3.0.txt",
                "LICENSES/Qt-6.11.2-Third-Party-Notices.txt",
            ],
        },
        {
            "name": "PyTorch CPU",
            "version": versions["torch"],
            "role": "required CPU tensor, Silero VAD, FunASR and audio runtime",
            "provenance": "official PyTorch CPU wheel installed in the build environment",
            "files": [
                _file_record(stage, runtime_base / "torch" / "lib" / "torch_cpu.dll")
            ],
            "license_files": [
                "runtime/Lib/site-packages/torch-2.14.0+cpu.dist-info/licenses/LICENSE"
            ],
        },
    ]
    for record in records:
        for relative_name in record["license_files"]:
            if not (stage / relative_name).is_file():
                raise RuntimeError(
                    f"Native component notice is missing for {record['name']}: "
                    f"{relative_name}"
                )
    (stage / "native-component-inventory.json").write_text(
        json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return records


def runtime_exclusion_inventory(stage: Path) -> None:
    records = [
        {
            "component": "PyAV and its bundled FFmpeg/codec libraries",
            "classification": "unused",
            "action": "excluded",
            "reason": "OneBoard captures 16 kHz mono audio and supplies NumPy arrays to faster-whisper; file/container decoding is outside the supported portable flow",
            "implementation": "the staged faster_whisper/audio.py is hash-gated and changed to import PyAV only when decode_audio is explicitly called",
        },
        {
            "component": "Qt Multimedia and Qt FFmpeg backend",
            "classification": "unused",
            "action": "excluded",
            "reason": "application source imports only QtCore, QtGui and QtWidgets",
        },
        {
            "component": "cuDNN/CUDA runtime DLLs",
            "classification": "unused in CPU portable build",
            "action": "excluded",
            "reason": "CTranslate2 CPU inference works with ctranslate2.dll, oneDNN and Intel OpenMP; no NVIDIA runtime is bundled",
        },
        {
            "component": "Numba/LLVM",
            "classification": "required",
            "action": "retained",
            "reason": "FunASR/librosa model paths import Numba and llvmlite at runtime",
        },
        {
            "component": "ModelScope",
            "classification": "required",
            "action": "retained",
            "reason": "supported FunASR and explicit ModelScope model-management paths use it dynamically",
        },
        {
            "component": "pip/ensurepip, CPython debug/test helpers, package tests, ONNX sample datasets and native development files",
            "classification": "unused",
            "action": "excluded",
            "reason": "customer runtime performs no installation, development, testing or model conversion",
        },
    ]
    (stage / "runtime-exclusions.json").write_text(
        json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def verify_runtime_policy(stage: Path) -> None:
    """Fail closed when an RC2 blocker or reviewed non-runtime tree reappears."""
    runtime = stage / "runtime"
    site_packages = runtime / "Lib" / "site-packages"
    forbidden_paths = (
        Path("Lib/ensurepip"),
        Path("Lib/site-packages/av"),
        Path("Lib/site-packages/av.libs"),
        Path("Lib/site-packages/pip"),
        Path("Lib/site-packages/onnxruntime/datasets"),
        Path("Lib/site-packages/torch/bin"),
        Path("Lib/site-packages/torch/include"),
        Path("Lib/site-packages/torch/share"),
        Path("Lib/site-packages/PyQt6/bindings"),
        Path("Lib/site-packages/PyQt6/lupdate"),
        Path("Lib/site-packages/PyQt6/uic"),
        Path("Lib/site-packages/PyQt6/Qt6/qml"),
        Path("Lib/site-packages/PyQt6/Qt6/qsci"),
        Path("Lib/site-packages/PyQt6/Qt6/translations"),
    )
    violations = [str(path) for path in forbidden_paths if (runtime / path).exists()]
    for path in runtime.rglob("*"):
        if not path.is_file():
            continue
        lowered = path.name.lower()
        relative = path.relative_to(runtime).as_posix()
        if lowered.endswith((".lib", ".exp")) and "/torch/lib/" in f"/{relative}":
            violations.append(relative)
        if lowered.endswith((".dll", ".pyd")) and (
            re.match(
                r"(?:avcodec|avformat|avutil|swresample|swscale|cudnn|cublas|cudart|cufft|curand|cusolver|cusparse|nvrtc|nvjitlink)",
                lowered,
            )
            or "multimedia" in lowered
            or lowered.endswith("_d.pyd")
            or lowered.startswith("_test")
            or lowered == "_ctypes_test.pyd"
        ):
            violations.append(relative)
    for path in site_packages.iterdir():
        if excluded_runtime_entry(path.name):
            violations.append(path.relative_to(runtime).as_posix())
    qt_root = site_packages / "PyQt6" / "Qt6"
    actual_qt_dlls = {
        path.name for path in (qt_root / "bin").iterdir() if path.is_file()
    }
    if actual_qt_dlls != QT_DLLS:
        violations.append(
            "Qt bin allowlist mismatch: "
            f"missing={sorted(QT_DLLS - actual_qt_dlls)}, "
            f"unexpected={sorted(actual_qt_dlls - QT_DLLS)}"
        )
    actual_qt_plugins = {
        path.relative_to(qt_root / "plugins").as_posix()
        for path in (qt_root / "plugins").rglob("*.dll")
    }
    if actual_qt_plugins != QT_PLUGINS:
        violations.append(
            "Qt plugin allowlist mismatch: "
            f"missing={sorted(QT_PLUGINS - actual_qt_plugins)}, "
            f"unexpected={sorted(actual_qt_plugins - QT_PLUGINS)}"
        )
    pyqt_bindings = {
        path.name for path in (site_packages / "PyQt6").glob("*.pyd")
    }
    if pyqt_bindings != QT_BINDINGS:
        violations.append(
            "PyQt binding allowlist mismatch: "
            f"missing={sorted(QT_BINDINGS - pyqt_bindings)}, "
            f"unexpected={sorted(pyqt_bindings - QT_BINDINGS)}"
        )
    required = (
        site_packages / "ctranslate2" / "ctranslate2.dll",
        site_packages / "ctranslate2" / "libiomp5md.dll",
        site_packages / "faster_whisper" / "audio.py",
    )
    violations.extend(
        str(path.relative_to(runtime)) for path in required if not path.is_file()
    )
    if violations:
        raise RuntimeError(
            "Release runtime violates the reviewed CPU policy: "
            + ", ".join(violations[:20])
        )


def copy_release_notices(stage: Path, source_root: Path = ROOT) -> None:
    """Copy the mandatory project and upstream notices into a release stage."""
    missing = [
        source_root / relative
        for relative in RELEASE_NOTICE_FILES
        if not (source_root / relative).is_file()
    ]
    if missing:
        raise RuntimeError(
            "Required release notice files are missing: "
            + ", ".join(str(path) for path in missing)
        )
    for relative in RELEASE_NOTICE_FILES:
        destination = stage / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_root / relative, destination)


def create_portable_archive(stage: Path, output: Path, archive: Path) -> None:
    """Archive the complete verified stage, including nested license files."""
    with zipfile.ZipFile(
        archive,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=6,
        allowZip64=True,
    ) as zipped:
        for path in sorted(stage.rglob("*")):
            if path.is_file():
                zipped.write(path, path.relative_to(output))


def verify_stage_hygiene(stage: Path) -> None:
    """Fail closed if non-runtime Python artifacts reached the package stage."""
    violations = []
    for path in stage.rglob("*"):
        relative = path.relative_to(stage)
        parts = tuple(part.lower() for part in relative.parts)
        in_notice_tree = any(part in NOTICE_TREE_NAMES for part in parts)
        if "__pycache__" in parts:
            violations.append(relative)
        elif not in_notice_tree and any(
            part in NON_RUNTIME_TREE_NAMES for part in parts
        ):
            violations.append(relative)
        elif (
            path.is_file()
            and len(parts) >= 2
            and tuple(parts[-2:]) in NON_RUNTIME_PACKAGE_FILES
        ):
            violations.append(relative)
        elif path.is_file() and path.suffix.lower() in {".pyc", ".pyo"}:
            violations.append(relative)
    if violations:
        preview = ", ".join(str(path) for path in violations[:10])
        raise RuntimeError(f"Release stage contains non-runtime artifacts: {preview}")


def customer_read_me(version: str) -> str:
    """Return the customer-facing portable-package instructions."""
    return (
        f"{APP_NAME} {version}\n\nExtract the complete folder, then open {APP_SHORT_NAME}.exe.\n"
        "Python and runtime dependencies are included. No Git, pip, command prompt, or repository clone is needed.\n"
        "The first-run wizard guides audio, Ollama, and model setup. Model downloads require your approval.\n"
        f"Settings, models, logs and transcripts live in %LOCALAPPDATA%\\{APP_SHORT_NAME}.\n"
        "Keep that folder when upgrading or uninstalling if you want to preserve your data.\n"
        "This is the CPU portable package. It contains no CUDA, cuDNN, PyAV, FFmpeg or Qt Multimedia runtime and does not install Ollama or GPU drivers.\n"
        "OneBoard supplies decoded NumPy audio to faster-whisper; standalone media-file decoding through faster-whisper is not included.\n"
        "Corresponding source code is available with each binary release at its exact matching Git tag.\n"
        "See LICENSE, LICENSES/FunASR-MIT.txt, LICENSES/LiveTranslate-MIT.txt, the complete LICENSES directory, THIRD_PARTY_NOTICES.md, dependency-inventory.json, native-component-inventory.json, runtime-exclusions.json and runtime distribution license files.\n"
    )


def csharp_literal(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def compile_launcher(stage: Path, version: str, windows_version: str, icon: Path | None) -> None:
    compiler = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Microsoft.NET" / "Framework64" / "v4.0.30319" / "csc.exe"
    if not compiler.is_file():
        raise RuntimeError("Windows .NET Framework 4 C# compiler is missing. No system tools were installed.")
    attributes = stage.parent / f"{APP_SHORT_NAME}-assembly.cs"
    attributes.write_text(
        "using System.Reflection;\n"
        + "\n".join(f"[assembly: {attribute}({csharp_literal(value)})]" for attribute, value in {
            "AssemblyTitle": APP_NAME,
            "AssemblyProduct": APP_NAME,
            "AssemblyCompany": COMPANY_NAME,
            "AssemblyVersion": windows_version,
            "AssemblyFileVersion": windows_version,
            "AssemblyInformationalVersion": version,
        }.items()), encoding="utf-8",
    )
    command = [str(compiler), "/nologo", "/target:winexe", "/platform:x64", "/optimize+", "/reference:System.Windows.Forms.dll", f"/out:{stage / (APP_SHORT_NAME + '.exe')}", str(ROOT / "packaging" / "OneBoardLauncher.cs"), str(attributes)]
    if icon:
        command.append(f"/win32icon:{icon}")
    try:
        run(command)
    finally:
        attributes.unlink(missing_ok=True)


def verify_distribution(stage: Path, output: Path) -> dict:
    probe_root = output / ("smoke-" + uuid.uuid4().hex[:8])
    probe_root.mkdir()
    report = probe_root / "report.json"
    environment = os.environ.copy()
    environment["ONEBOARD_DATA_DIR"] = str(probe_root / "profile")
    environment["PATH"] = os.pathsep.join([str(Path(os.environ["WINDIR"]) / "System32"), os.environ["WINDIR"]])
    environment["PYTHONHOME"] = str(probe_root / "nonexistent-python")
    environment["PYTHONPATH"] = str(probe_root / "nonexistent-source")
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    print("Verifying launcher with no developer Python on PATH, offline, in a fresh profile...", flush=True)
    try:
        run([str(stage / f"{APP_SHORT_NAME}.exe"), "--smoke-test", str(report)], cwd=probe_root, env=environment, timeout=180)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        log_path = probe_root / "profile" / "logs" / "launcher.log"
        details = log_path.read_text(encoding="utf-8-sig") if log_path.exists() else "No launcher log was written."
        raise RuntimeError(f"Packaged smoke verification failed:\n{details}") from error
    result = json.loads(report.read_text(encoding="utf-8"))
    expected = (stage / "runtime" / "python.exe").resolve()
    if Path(result["executable"]).resolve() != expected or Path(result["worker"]["executable"]).resolve() != expected:
        raise RuntimeError("Smoke verification escaped the bundled runtime")
    if not result.get("ok"):
        raise RuntimeError("Smoke verification did not report success")
    (output / "packaging-smoke.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    shutil.rmtree(probe_root)
    return result


def build(args: argparse.Namespace) -> None:
    from version import VERSION, WINDOWS_VERSION

    if os.name != "nt" or struct.calcsize("P") != 8 or sys.version_info[:2] != (3, 12):
        raise RuntimeError("Build with 64-bit Windows Python 3.12 in the application virtual environment")
    if args.version and args.version != VERSION:
        raise ValueError("Change version.py first; --version must match the centralized VERSION")
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:-[A-Za-z0-9.]+)?", VERSION) or not re.fullmatch(r"\d+\.\d+\.\d+\.\d+", WINDOWS_VERSION):
        raise ValueError("version.py must supply a safe release VERSION and numeric WINDOWS_VERSION")
    validate_artifact_version(
        VERSION, skip_archive=args.skip_archive, iscc=args.iscc
    )
    dirty = bool(run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True).stdout.strip())
    if dirty and not args.allow_dirty:
        raise RuntimeError("Commit intended source changes first, or use --allow-dirty for a clearly marked QA build")
    run([sys.executable, "-m", "pip", "check"])
    output = ROOT / "release"
    output.mkdir(exist_ok=True)
    if output.resolve() != ROOT.resolve() / "release":
        raise ValueError("The release output must remain inside the developer checkout")
    stage = output / APP_SHORT_NAME
    archive = output / f"{APP_SHORT_NAME}-{VERSION}-win-x64.zip"
    installer = output / f"{APP_SHORT_NAME}-Setup-{VERSION}.exe"
    smoke_report = output / "packaging-smoke.json"
    expected_artifacts = {archive.name, installer.name, smoke_report.name}
    for artifact in (archive, installer, smoke_report):
        remove_stale_artifact(artifact, output, expected_artifacts)
    remove_stage(stage, output)
    (stage / "app").mkdir(parents=True)
    tracked = run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True).stdout.split("\0")
    # A preview may contain new OneBoard modules still awaiting phase commits.
    if args.allow_dirty:
        tracked += [str(path.relative_to(ROOT)) for path in ROOT.glob("oneboard_*.py")]
        tracked += ["version.py"]
    for name in sorted(set(tracked)):
        relative = Path(name)
        if not name or not application_file(relative):
            continue
        destination = stage / "app" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    if not (stage / "app" / "oneboard_launch.py").is_file():
        raise RuntimeError("oneboard_launch.py is not tracked; commit packaging before a release build")
    copy_release_notices(stage)
    revision = run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True).stdout.strip()
    (stage / "distribution.json").write_text(json.dumps({"product": APP_NAME, "identifier": APP_SHORT_NAME, "version": VERSION, "windows_version": WINDOWS_VERSION, "source_commit": revision, "dirty_preview": dirty, "python": sys.version.split()[0], "architecture": "win-x64", "models_bundled": False}, indent=2), encoding="utf-8")
    print("Copying CPython and installed runtime dependencies (model caches are excluded)...", flush=True)
    copy_runtime(stage / "runtime")
    prune_runtime(stage / "runtime")
    verify_runtime_policy(stage)
    dependencies = dependency_inventory(stage)
    native_component_inventory(stage, dependencies)
    runtime_exclusion_inventory(stage)
    icon = Path(args.icon).resolve() if args.icon else None
    if icon and (not icon.is_file() or icon.suffix.lower() != ".ico"):
        raise ValueError("--icon must identify an existing Windows .ico asset")
    compile_launcher(stage, VERSION, WINDOWS_VERSION, icon)
    (stage / "READ_ME.txt").write_text(customer_read_me(VERSION), encoding="utf-8")
    verify_stage_hygiene(stage)
    smoke = verify_distribution(stage, output)
    print(f'Packaged verification passed ({smoke["torch"]}, Qt {smoke["qt_platform"]}).', flush=True)
    verify_stage_hygiene(stage)
    verify_runtime_policy(stage)
    if not args.skip_archive:
        print(f"Creating {archive.name}...", flush=True)
        create_portable_archive(stage, output, archive)
        print(f"Portable release: {archive} ({archive.stat().st_size / 1024**2:.1f} MiB)", flush=True)
    if args.iscc:
        compiler = Path(args.iscc).resolve()
        if not compiler.is_file():
            raise ValueError("--iscc must identify an existing Inno Setup 6.3+ ISCC.exe")
        command = [str(compiler), f"/DStageDir={stage}", f"/DOutputDir={output}", f"/DAppName={APP_NAME}", f"/DAppIdName={APP_SHORT_NAME}", f"/DCompanyName={COMPANY_NAME}", f"/DAppVersion={VERSION}", f"/DWindowsVersion={WINDOWS_VERSION}"]
        if icon:
            command.append(f"/DIconFile={icon}")
        run(command + [str(ROOT / "packaging" / "OneBoardLiveTranslate.iss")])
    else:
        print("Installer not built: supply --iscc with an existing Inno Setup 6.3+ compiler. No system tools were installed.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", help="Optional assertion of version.py VERSION")
    parser.add_argument("--icon", help="Optional OneBoard .ico asset used for application and installer")
    parser.add_argument("--iscc", help="Path to an already available Inno Setup 6.3+ ISCC.exe")
    parser.add_argument("--allow-dirty", action="store_true", help="Build working source for QA and mark distribution as dirty_preview")
    parser.add_argument("--skip-archive", action="store_true", help="Build and verify the application directory only")
    build(parser.parse_args())

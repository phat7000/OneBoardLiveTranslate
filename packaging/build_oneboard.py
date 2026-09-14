"""Build a relocatable Windows distribution using a prepared developer venv.

This deliberately reuses upstream's ordinary Python modules and full dependency
environment instead of freezing dynamic ASR/model imports into one executable.
No installer, package manager, or model download runs on the customer's machine.
"""

from __future__ import annotations

import argparse
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
REVOKED_RELEASE_VERSIONS = {"0.2.0-rc1"}
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
    Path("LICENSES") / "FunASR-MIT.txt",
    Path("LICENSES") / "LiveTranslate-MIT.txt",
    Path("THIRD_PARTY_NOTICES.md"),
)


def canonical_distribution_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


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
        or canonical_distribution_name(name.split("-", 1)[0].lstrip("_"))
        in DEVELOPMENT_DISTRIBUTIONS
        or name.endswith((".pyc", ".pyo", ".pdb"))
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
            ignored.update({"site-packages", "test", "idlelib", "tkinter", "turtledemo"} & set(names))
        return ignored

    shutil.copytree(base / "Lib", runtime / "Lib", ignore=ignore_standard)
    shutil.copytree(site_packages, runtime / "Lib" / "site-packages", ignore=ignored_runtime_files)
    # Explicit isolated search paths prohibit registry/system-Python/user-site
    # fallback and remain valid after moving the extracted application folder.
    (runtime / f"python{sys.version_info.major}{sys.version_info.minor}._pth").write_text(
        ".\nDLLs\nLib\nLib/site-packages\n../app\nimport site\n", encoding="ascii"
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
    if missing:
        raise RuntimeError(
            "Dependency inventory references missing license/notice files: "
            + ", ".join(missing[:10])
        )


def dependency_inventory(stage: Path) -> None:
    records = []
    for distribution in sorted(importlib.metadata.distributions(), key=lambda item: item.metadata["Name"].lower()):
        metadata = distribution.metadata
        if canonical_distribution_name(metadata["Name"]) in DEVELOPMENT_DISTRIBUTIONS:
            continue
        records.append({
            "name": metadata["Name"],
            "version": distribution.version,
            "license_expression": metadata.get("License-Expression"),
            "license": metadata.get("License"),
            "license_classifiers": [item for item in metadata.get_all("Classifier", []) if item.startswith("License ::")],
            "license_files": distribution_notice_files(distribution.files),
        })
    verify_dependency_notice_inventory(stage, records)
    (stage / "dependency-inventory.json").write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    (stage / "runtime-requirements.txt").write_text(
        "# Exact installed distributions copied by this build; model weights are separate.\n"
        + "\n".join(f'{record["name"]}=={record["version"]}' for record in records) + "\n",
        encoding="utf-8",
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
        "This package does not install Ollama or GPU drivers. CPU and GPU builds depend on the runtime selected by the publisher.\n"
        "Corresponding source code is available with each binary release at its exact matching Git tag.\n"
        "See LICENSE, LICENSES/FunASR-MIT.txt, LICENSES/LiveTranslate-MIT.txt, THIRD_PARTY_NOTICES.md, dependency-inventory.json and runtime distribution license files.\n"
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
    dependency_inventory(stage)
    icon = Path(args.icon).resolve() if args.icon else None
    if icon and (not icon.is_file() or icon.suffix.lower() != ".ico"):
        raise ValueError("--icon must identify an existing Windows .ico asset")
    compile_launcher(stage, VERSION, WINDOWS_VERSION, icon)
    (stage / "READ_ME.txt").write_text(customer_read_me(VERSION), encoding="utf-8")
    smoke = verify_distribution(stage, output)
    print(f'Packaged verification passed ({smoke["torch"]}, Qt {smoke["qt_platform"]}).', flush=True)
    verify_stage_hygiene(stage)
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

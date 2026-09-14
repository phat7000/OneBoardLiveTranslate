"""Regression coverage for release isolation and user-data preservation."""

import importlib.util
import zipfile
from pathlib import Path

import pytest

import oneboard_paths


def load_builder():
    source = Path(__file__).resolve().parents[1] / "packaging" / "build_oneboard.py"
    spec = importlib.util.spec_from_file_location("oneboard_release_builder", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def local_paths(tmp_path, monkeypatch):
    source = tmp_path / "checkout"
    source.mkdir()
    monkeypatch.setattr(oneboard_paths, "__file__", str(source / "oneboard_paths.py"))
    monkeypatch.delenv("ONEBOARD_DATA_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local-data"))
    return source


def test_developer_data_stays_in_checkout(local_paths):
    assert oneboard_paths.data_dir() == local_paths


def test_packaged_data_survives_relocation(local_paths, monkeypatch):
    packaged_app = local_paths.parent / "app"
    packaged_app.mkdir()
    monkeypatch.setattr(oneboard_paths, "__file__", str(packaged_app / "oneboard_paths.py"))
    (packaged_app.parent / "distribution.json").write_text("{}")
    expected = local_paths.parent / "local-data" / "OneBoardLiveTranslate"
    assert oneboard_paths.data_dir() == expected
    (expected / "user_settings.json").write_text('{"first_run_completed": true}')
    new_application = local_paths.parent / "replacement" / "app"
    new_application.mkdir(parents=True)
    (new_application.parent / "distribution.json").write_text("{}")
    monkeypatch.setattr(oneboard_paths, "__file__", str(new_application / "oneboard_paths.py"))
    assert oneboard_paths.data_dir() == expected
    assert (expected / "user_settings.json").read_text() == '{"first_run_completed": true}'


def test_unrelated_parent_marker_does_not_change_checkout_paths(local_paths):
    (local_paths.parent / "distribution.json").write_text("{}")
    assert oneboard_paths.data_dir() == local_paths


def test_explicit_profile_is_independent(local_paths, monkeypatch):
    profile = local_paths.parent / "portable profile"
    monkeypatch.setenv("ONEBOARD_DATA_DIR", str(profile))
    assert oneboard_paths.data_dir() == profile
    assert profile.is_dir()


def test_relative_profile_is_rejected(local_paths, monkeypatch):
    monkeypatch.setenv("ONEBOARD_DATA_DIR", "relative-state")
    with pytest.raises(ValueError, match="absolute"):
        oneboard_paths.data_dir()


@pytest.mark.parametrize("name", ["main.py", "oneboard_display_window.py", "oneboard_launch.py", "oneboard_log_safety.py", "version.py", "config.yaml", "i18n/en.json", "funasr_nano/tools/utils.py"])
def test_builder_includes_application(name):
    assert load_builder().application_file(Path(name))


@pytest.mark.parametrize("name", [".git/config", "models/model.bin", "logs/log.txt", "user_settings.json", "tests/test_main.py", "test_audio.py", "test_future.py", "funasr_nano/tests/fixture.py", "funasr_nano/__pycache__/cached.pyc", "exports/source.zip", "release/old-release.zip", "start.bat", "update.bat", "install.ps1", "build_oneboard_release.ps1", "packaging/build_oneboard.py"])
def test_builder_excludes_developer_and_runtime_state(name):
    assert not load_builder().application_file(Path(name))


def test_stage_cleanup_cannot_escape_output(tmp_path):
    output = tmp_path / "release"
    output.mkdir()
    user_data = tmp_path / "OneBoardLiveTranslate"
    user_data.mkdir()
    keep = user_data / "keep.txt"
    keep.write_text("keep")
    with pytest.raises(ValueError, match="unexpected"):
        load_builder().remove_stage(user_data, output)
    assert keep.read_text() == "keep"


def test_stage_cleanup_only_removes_oneboard_stage(tmp_path):
    stage = tmp_path / "OneBoardLiveTranslate"
    stage.mkdir()
    (stage / "old.txt").write_text("old")
    load_builder().remove_stage(stage, tmp_path)
    assert not stage.exists()


def test_only_exact_stale_release_artifacts_are_removed(tmp_path):
    builder = load_builder()
    stale = tmp_path / "OneBoardLiveTranslate-0.2.0-win-x64.zip"
    stale.write_text("stale")
    builder.remove_stale_artifact(stale, tmp_path, {stale.name})
    assert not stale.exists()

    unrelated = tmp_path / "customer-data.zip"
    unrelated.write_text("keep")
    with pytest.raises(ValueError, match="unexpected"):
        builder.remove_stale_artifact(unrelated, tmp_path, {stale.name})
    assert unrelated.read_text() == "keep"


def test_artifact_cleanup_refuses_directories(tmp_path):
    builder = load_builder()
    directory = tmp_path / "OneBoardLiveTranslate-0.2.0-win-x64.zip"
    directory.mkdir()
    with pytest.raises(ValueError, match="directory"):
        builder.remove_stale_artifact(directory, tmp_path, {directory.name})
    assert directory.is_dir()


def test_dependency_copy_preserves_licenses():
    ignored = load_builder().ignored_runtime_files("unused", ["__pycache__", "cached.pyc", "direct_url.json", "LICENSE", "licenses", "NOTICE", "METADATA", "package.py"])
    assert ignored == {"__pycache__", "cached.pyc", "direct_url.json"}


def test_dependency_copy_preserves_test_named_directories_below_license_tree():
    ignored = load_builder().ignored_runtime_files(
        "site-packages/torch.dist-info/licenses/third_party/fbgemm/fbgemm_gpu",
        ["test", "__pycache__", "LICENSE"],
    )

    assert ignored == {"__pycache__"}


def test_dependency_copy_excludes_only_the_known_transformers_test_helper():
    ignored = load_builder().ignored_runtime_files(
        "site-packages/transformers",
        ["testing_utils.py", "utils.py", "modeling_utils.py"],
    )

    assert ignored == {"testing_utils.py"}


def test_revoked_version_allows_only_unarchived_staging_smoke():
    builder = load_builder()

    builder.validate_artifact_version(
        "0.2.0-rc1", skip_archive=True, iscc=None
    )
    with pytest.raises(RuntimeError, match="version 0.2.0-rc1 is revoked"):
        builder.validate_artifact_version(
            "0.2.0-rc1", skip_archive=False, iscc=None
        )
    with pytest.raises(RuntimeError, match="version 0.2.0-rc1 is revoked"):
        builder.validate_artifact_version(
            "0.2.0-rc1", skip_archive=True, iscc="ISCC.exe"
        )
    builder.validate_artifact_version(
        "1.0.0", skip_archive=False, iscc="ISCC.exe"
    )


def test_dependency_inventory_filters_cache_noise_from_notice_paths():
    files = [
        Path("package.dist-info/licenses/LICENSE"),
        Path("package/__pycache__/license.cpython-312.pyc"),
        Path("package/license_helper.py"),
    ]

    assert load_builder().distribution_notice_files(files) == [
        str(Path("package.dist-info/licenses/LICENSE")),
        str(Path("package/license_helper.py")),
    ]


def test_dependency_inventory_requires_each_notice_in_stage(tmp_path):
    builder = load_builder()
    stage = tmp_path / "stage"
    relative = Path("package.dist-info/licenses/vendor/test/LICENSE")
    notice = stage / "runtime" / "Lib" / "site-packages" / relative
    notice.parent.mkdir(parents=True)
    notice.write_text("license", encoding="utf-8")
    records = [{"name": "package", "license_files": [str(relative)]}]

    builder.verify_dependency_notice_inventory(stage, records)

    notice.unlink()
    with pytest.raises(RuntimeError, match="missing license/notice files"):
        builder.verify_dependency_notice_inventory(stage, records)


def test_dependency_inventory_rejects_notice_paths_outside_runtime(tmp_path):
    records = [{"name": "package", "license_files": ["../../../../outside/LICENSE"]}]

    with pytest.raises(RuntimeError, match="outside runtime"):
        load_builder().verify_dependency_notice_inventory(tmp_path / "stage", records)


def test_release_notices_are_mandatory_and_preserve_layout(tmp_path):
    builder = load_builder()
    source = tmp_path / "source"
    stage = tmp_path / "stage"
    expected = {
        Path("LICENSE"): "GPL project license",
        Path("LICENSES/FunASR-MIT.txt"): "FunASR MIT attribution",
        Path("LICENSES/LiveTranslate-MIT.txt"): "upstream MIT attribution",
        Path("THIRD_PARTY_NOTICES.md"): "dependency notices",
    }
    for relative, content in expected.items():
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    builder.copy_release_notices(stage, source)

    assert {relative: (stage / relative).read_text(encoding="utf-8") for relative in expected} == expected

    (source / "LICENSES/FunASR-MIT.txt").unlink()
    with pytest.raises(RuntimeError, match=r"LICENSES[/\\]FunASR-MIT\.txt"):
        builder.copy_release_notices(tmp_path / "incomplete-stage", source)


def test_checkout_release_notices_can_be_staged(tmp_path):
    builder = load_builder()
    stage = tmp_path / "stage"

    builder.copy_release_notices(stage)

    for relative in builder.RELEASE_NOTICE_FILES:
        assert (stage / relative).read_bytes() == (builder.ROOT / relative).read_bytes()


def test_portable_archive_contains_all_notice_files(tmp_path):
    builder = load_builder()
    output = tmp_path / "release"
    stage = output / "OneBoardLiveTranslate"
    source = tmp_path / "source"
    for relative in builder.RELEASE_NOTICE_FILES:
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(relative.as_posix(), encoding="utf-8")
    builder.copy_release_notices(stage, source)
    runtime_notices = (
        Path("runtime/LICENSE.txt"),
        Path("runtime/Lib/site-packages/example.dist-info/NOTICE"),
    )
    for relative in runtime_notices:
        path = stage / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(relative.as_posix(), encoding="utf-8")
    archive = output / "OneBoardLiveTranslate-test-win-x64.zip"

    builder.create_portable_archive(stage, output, archive)

    with zipfile.ZipFile(archive) as packaged:
        names = set(packaged.namelist())
    expected = {
        (Path(stage.name) / relative).as_posix()
        for relative in (*builder.RELEASE_NOTICE_FILES, *runtime_notices)
    }
    assert expected <= names


def test_customer_readme_exposes_source_and_all_license_records():
    readme = load_builder().customer_read_me("1.0.0")

    assert "exact matching Git tag" in readme
    assert "LICENSE" in readme
    assert "LICENSES/FunASR-MIT.txt" in readme
    assert "LICENSES/LiveTranslate-MIT.txt" in readme
    assert "THIRD_PARTY_NOTICES.md" in readme


def test_installer_recursively_includes_verified_stage_and_displays_gpl_license():
    installer = Path("packaging/OneBoardLiveTranslate.iss").read_text(encoding="utf-8")
    assert r"LicenseFile={#StageDir}\LICENSE" in installer
    assert r'Source: "{#StageDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs' in installer


def test_dependency_copy_excludes_development_only_packages_and_test_trees():
    ignored = load_builder().ignored_runtime_files(
        "unused",
        ["pytest", "pytest-9.1.1.dist-info", "_pytest", "pluggy", "iniconfig", "tests", "_tests", "testdata", "SelfTest", "runtime.py"],
    )
    assert ignored == {
        "pytest", "pytest-9.1.1.dist-info", "_pytest", "pluggy", "iniconfig", "tests", "_tests", "testdata", "SelfTest",
    }


@pytest.mark.parametrize(
    "relative",
    [
        Path("app/__pycache__/module.pyc"),
        Path("runtime/Lib/package/tests/fixture.py"),
        Path("runtime/Lib/sniffio/_tests/test_sniffio.py"),
        Path("runtime/Lib/google/protobuf/testdata/sample.proto"),
        Path("runtime/Lib/site-packages/Crypto/SelfTest/test_hash.py"),
        Path("runtime/Lib/site-packages/transformers/testing_utils.py"),
        Path("runtime/Lib/cached.pyo"),
    ],
)
def test_release_stage_hygiene_rejects_non_runtime_python_artifacts(tmp_path, relative):
    stage = tmp_path / "stage"
    path = stage / relative
    path.parent.mkdir(parents=True)
    path.write_text("not runtime", encoding="utf-8")

    with pytest.raises(RuntimeError, match="non-runtime artifacts"):
        load_builder().verify_stage_hygiene(stage)


def test_release_stage_hygiene_accepts_runtime_and_notices(tmp_path):
    stage = tmp_path / "stage"
    for relative in (
        Path("app/main.py"),
        Path("runtime/Lib/package/module.py"),
        Path("LICENSE"),
        Path(
            "runtime/Lib/site-packages/torch.dist-info/licenses/third_party/"
            "fbgemm/fbgemm_gpu/test/quantize/mx/LICENSE"
        ),
    ):
        path = stage / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("runtime", encoding="utf-8")

    load_builder().verify_stage_hygiene(stage)


def test_release_workflow_is_manual_and_uses_only_oneboard_builder():
    workflow = Path(".github/workflows/release.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in workflow
    assert "  push:" not in workflow
    assert "action-gh-release" not in workflow
    assert "build_release.ps1" not in workflow
    assert "build_oneboard_release.ps1" in workflow
    assert "OneBoardLiveTranslate-release-candidate" in workflow


def test_readme_customer_path_uses_oneboard_executable():
    for name in ("README.md", "README_zh.md"):
        readme = Path(name).read_text(encoding="utf-8")
        assert "LiveTranslate-portable-*.zip" not in readme
        assert "OneBoardLiveTranslate.exe" in readme
        assert "update.bat` is not a customer updater" in readme or "`update.bat` 不是客户更新程序" in readme


def test_developer_updater_docs_describe_tracking_branch_semantics():
    readme = Path("README.md").read_text(encoding="utf-8")
    updates = Path("ONEBOARD_UPDATES.md").read_text(encoding="utf-8")
    readme_zh = Path("README_zh.md").read_text(encoding="utf-8")

    assert "configured tracking branch" in readme
    assert "configured tracking branch" in updates
    assert "当前分支所配置的跟踪分支" in readme_zh


def test_release_docs_never_instruct_rebuilding_revoked_rc1():
    for name in ("PACKAGING.md", "RELEASE_READINESS.md", "PHASE2_FINAL_REPORT.md"):
        document = Path(name).read_text(encoding="utf-8")
        assert "-Version 0.2.0-rc1" not in document
        assert "new approved" in document

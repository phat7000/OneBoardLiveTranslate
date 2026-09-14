"""Regression coverage for a clean public source snapshot."""

import ast
import hashlib
import logging
import re
import subprocess
import sys
from pathlib import Path

import pytest

import model_manager
import translator as translator_module
from oneboard_log_safety import RedactingFormatter, redact_sensitive_text
from translator import Translator


ROOT = Path(__file__).resolve().parents[1]
HIGH_CONFIDENCE_SECRET_PATTERNS = {
    "OpenAI-style token": re.compile(rb"\b" + b"sk-" + rb"[A-Za-z0-9_:\-]{16,}\b"),
    "GitHub token": re.compile(rb"\b" + b"gh" + rb"[pousr]_[A-Za-z0-9]{30,}\b"),
    "GitHub fine-grained token": re.compile(rb"\b" + b"github_pat_" + rb"[A-Za-z0-9_]{20,}\b"),
    "GitLab token": re.compile(rb"\b" + b"glpat-" + rb"[A-Za-z0-9_-]{20,}\b"),
    "Hugging Face token": re.compile(rb"\b" + b"hf_" + rb"[A-Za-z0-9]{20,}\b"),
    "npm token": re.compile(rb"\b" + b"npm_" + rb"[A-Za-z0-9]{20,}\b"),
    "AWS access key": re.compile(rb"\bA(?:KI|SI)A[A-Z0-9]{16}\b"),
    "AWS secret access key": re.compile(
        rb"(?i)\bAWS_SECRET_ACCESS_KEY\b\s*[:=]\s*[\"']?[A-Za-z0-9/+=]{40}\b"
    ),
    "Google API key": re.compile(rb"\bAIza[0-9A-Za-z_-]{35}\b"),
    "Slack token": re.compile(rb"\bxox[baprs]-[0-9A-Za-z-]{20,}\b"),
    "private key": re.compile(b"-" * 5 + rb"BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY"),
}


def tracked_files():
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    for name in result.stdout.rstrip(b"\0").split(b"\0"):
        if not name:
            continue
        yield ROOT / name.decode("utf-8")


def test_public_source_candidates_contain_no_high_confidence_secret():
    findings = []
    for path in tracked_files():
        content = path.read_bytes()
        for label, pattern in HIGH_CONFIDENCE_SECRET_PATTERNS.items():
            if pattern.search(content):
                findings.append(f"{path.relative_to(ROOT)}: {label}")
    assert not findings, "potential credentials in tracked source: " + ", ".join(findings)


def test_lm_studio_first_run_default_has_no_api_key():
    tree = ast.parse((ROOT / "main.py").read_text(encoding="utf-8"))
    defaults = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        values = {
            key.value: value.value
            for key, value in zip(node.keys, node.values)
            if isinstance(key, ast.Constant)
            and isinstance(key.value, str)
            and isinstance(value, ast.Constant)
            and isinstance(value.value, str)
        }
        if values.get("api_base") == "http://127.0.0.1:1234/v1":
            defaults.append(values)

    assert defaults
    assert all(default.get("api_key") == "" for default in defaults)


def test_vendored_funasr_provenance_and_license_are_pinned():
    expected_blobs = {
        "funasr_nano/__init__.py": "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391",
        "funasr_nano/ctc.py": "f2d592759b98e1b62a7f4580e25ced395f8cfaf7",
        "funasr_nano/model.py": "49213ef8941d81e04a68495e310cffe012637a1d",
        "funasr_nano/tools/__init__.py": "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391",
        "funasr_nano/tools/utils.py": "7125bca5c7f68dc165cf7803ae6927fdda67a8e4",
    }
    for name, expected in expected_blobs.items():
        result = subprocess.run(
            ["git", "hash-object", "--", name],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        assert result.stdout.strip() == expected

    license_bytes = (
        (ROOT / "LICENSES/FunASR-MIT.txt")
        .read_bytes()
        .replace(b"\r\n", b"\n")
        .removesuffix(b"\n")
    )
    assert hashlib.sha256(license_bytes).hexdigest() == (
        "f382b62dcc61fc566b9215b1e3b604b539bfd96ed52ae1eeff5090f6dc176057"
    )
    notice = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    assert "335eb1ea6156bc353283e21ae121a2224aa79175" in notice
    assert "d536d55c71d040d654292cae8c716266d71c6779" in notice
    assert all(name in notice for name in expected_blobs)


def test_required_private_file_patterns_are_ignored():
    names = [
        ".env",
        ".env.local",
        "credentials.json",
        "secrets.json",
        "identity.pem",
        "private.key",
        "certificate.p12",
        "certificate.pfx",
        ".mypy_cache/state",
        ".ruff_cache/state",
        ".coverage",
        "htmlcov/index.html",
        "exports/public-source.zip",
        "release/old.zip",
        "release/old.exe",
    ]
    missing = []
    for name in names:
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", "--quiet", "--", name],
            cwd=ROOT,
        )
        if result.returncode != 0:
            missing.append(name)
    assert not missing, f"required ignore patterns missing for: {missing}"


def test_source_documentation_directory_is_not_blanket_ignored():
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "--quiet", "--", "docs/public-guide.md"],
        cwd=ROOT,
    )
    assert result.returncode == 1


def test_translator_logs_do_not_serialize_user_request_payload(monkeypatch, caplog):
    monkeypatch.setattr(
        translator_module,
        "make_openai_client",
        lambda *args, **kwargs: object(),
    )
    sentinel = "credential-value-that-must-not-be-logged"
    with caplog.at_level(logging.INFO, logger="LiveTranslate.TL"):
        Translator(
            api_base="https://provider.example/v1",
            api_key="test-key",
            model="test-model",
            overrides={"temperature": 0.25},
            extra_body={"authorization": sentinel, "nested": {"token": sentinel}},
        )

    assert sentinel not in caplog.text
    assert "0.25" not in caplog.text
    assert "extra_body configured" in caplog.text


def test_download_proxy_log_does_not_expose_credentials(caplog):
    sentinel = "proxy-password-that-must-not-be-logged"
    proxy = f"http://proxy-user:{sentinel}@proxy.example:8080"
    with caplog.at_level(logging.INFO, logger="LiveTranslate.ModelManager"):
        with model_manager._proxy_env(proxy):
            pass

    assert sentinel not in caplog.text
    assert proxy not in caplog.text
    assert "custom" in caplog.text


def test_configuration_logging_uses_fixed_messages_only():
    panel = (ROOT / "control_panel.py").read_text(encoding="utf-8")
    assert 'log.info("Settings applied")' in panel
    assert "Settings applied: {" not in panel

    for name in ("install.ps1", "build_release.ps1"):
        script = (ROOT / name).read_text(encoding="utf-8")
        assert 'system proxy: $https' not in script

    assert "force=True" in (ROOT / "main.py").read_text(encoding="utf-8")
    assert "force=True" in (ROOT / "asr_worker.py").read_text(encoding="utf-8")


def test_diagnostic_redaction_covers_payloads_urls_and_tracebacks():
    sentinel = "credential-value-that-must-not-be-logged"
    unsafe = (
        f'https://proxy-user:{sentinel}@proxy.example:8080 '
        f'Authorization: Bearer {sentinel} '
        f'{{"extra_body": {{"token": "{sentinel}"}}}}'
    )
    assert sentinel not in redact_sensitive_text(unsafe)

    try:
        raise RuntimeError(unsafe)
    except RuntimeError:
        record = logging.LogRecord(
            "test",
            logging.ERROR,
            __file__,
            1,
            "provider failed: %s",
            (unsafe,),
            sys.exc_info(),
        )
    rendered = RedactingFormatter("%(message)s").format(record)

    assert sentinel not in rendered
    assert "<redacted>" in rendered


@pytest.mark.parametrize(
    "unsafe",
    [
        "Authorization: Token credential-value-that-must-not-be-logged",
        "Authorization: ApiKey credential-value-that-must-not-be-logged",
        "API key: credential-value-that-must-not-be-logged",
        'api_key: "\ncredential-value-that-must-not-be-logged"',
        "vendor_credential=credential-value-that-must-not-be-logged",
        "credentials=credential-value-that-must-not-be-logged",
        "OPENAI_API_KEY=credential-value-that-must-not-be-logged",
        "DB_PASSWORD=credential-value-that-must-not-be-logged",
        "VENDOR_ACCESS_TOKEN=credential-value-that-must-not-be-logged",
        "PROXY_PASSWORD=credential-value-that-must-not-be-logged",
        "AWS_SECRET_ACCESS_KEY=credential-value-that-must-not-be-logged",
        "HTTPS_PROXY=proxy-user:credential-value-that-must-not-be-logged@proxy.example:8080",
    ],
)
def test_diagnostic_redaction_covers_common_credential_variants(unsafe):
    assert "credential-value-that-must-not-be-logged" not in redact_sensitive_text(
        unsafe
    )


def test_stderr_capture_redacts_before_forwarding():
    import io

    from dialogs import _StderrCapture

    sentinel = "credential-value-that-must-not-be-logged"
    original = io.StringIO()
    captured = []
    stream = _StderrCapture(captured.append, original)

    stream.write(f"api_key={sentinel}\n")

    assert sentinel not in original.getvalue()
    assert all(sentinel not in line for line in captured)
    assert "<redacted>" in original.getvalue()
    assert any("<redacted>" in line for line in captured)


@pytest.mark.parametrize(
    "chunks",
    [
        ("api_key=", "credential-value-that-must-not-be-logged", "\n"),
        (
            "HTTPS_PROXY=proxy-user:",
            "credential-value-that-must-not-be-logged",
            "@proxy.example:8080",
            "\r",
        ),
    ],
)
def test_stderr_capture_redacts_values_split_across_writes(chunks):
    import io

    from dialogs import _StderrCapture

    sentinel = "credential-value-that-must-not-be-logged"
    original = io.StringIO()
    captured = []
    stream = _StderrCapture(captured.append, original)

    for chunk in chunks:
        stream.write(chunk)
    stream.flush()

    assert sentinel not in original.getvalue()
    assert all(sentinel not in line for line in captured)
    assert "<redacted>" in original.getvalue()
    assert any("<redacted>" in line for line in captured)


def test_stderr_capture_keeps_partial_record_across_flushes():
    import io

    from dialogs import _StderrCapture

    sentinel = "credential-value-that-must-not-be-logged"
    original = io.StringIO()
    captured = []
    stream = _StderrCapture(captured.append, original)

    stream.write("api_key=")
    stream.flush()
    stream.write(sentinel)
    stream.flush()
    assert original.getvalue() == ""
    assert captured == []

    stream.finish()

    assert sentinel not in original.getvalue()
    assert all(sentinel not in line for line in captured)
    assert "<redacted>" in original.getvalue()


def test_stderr_capture_normalizes_ansi_before_redaction():
    import io

    from dialogs import _StderrCapture

    sentinel = "credential-value-that-must-not-be-logged"
    original = io.StringIO()
    captured = []
    stream = _StderrCapture(captured.append, original)

    stream.write(f"api_\x1b[31mkey=\x1b[0m{sentinel}\n")

    assert sentinel not in original.getvalue()
    assert all(sentinel not in line for line in captured)
    assert "\x1b" not in original.getvalue()
    assert "<redacted>" in original.getvalue()

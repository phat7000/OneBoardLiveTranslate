import json
import os

import httpx
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from branding import APP_NAME, PROJECT_LICENSE, UPSTREAM_PROJECT_NAME
from oneboard_updates import UpdateDialog, check_for_updates


def test_disabled_updates_never_make_network_requests():
    def forbidden(**kwargs):
        raise AssertionError("Disabled update check made a network request")
    assert check_for_updates({}, client_factory=forbidden).status == "disabled"
    assert check_for_updates({"oneboard_update_enabled": True}, client_factory=forbidden).status == "disabled"


def check_manifest(payload, **settings):
    body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=body))
    return check_for_updates({
        "oneboard_update_enabled": True,
        "oneboard_update_manifest_url": "https://releases.example.test/manifest.json",
        **settings,
    }, client_factory=lambda **kwargs: httpx.Client(transport=transport, **kwargs))


def test_new_oneboard_release_is_offered_without_installing():
    result = check_manifest({"version": "1.1.0", "channel": "stable",
                             "release_url": "https://releases.example.test/1.1.0"})
    assert result.status == "available"
    assert result.version == "1.1.0"
    assert result.release_url.endswith("/1.1.0")


@pytest.mark.parametrize("version", ["0.1.0", "0.2.0-rc1", "0.2.0-beta9"])
def test_older_and_same_releases_are_current(version):
    assert check_manifest({"version": version, "channel": "stable",
                           "release_url": "https://releases.example.test/"}).status == "current"


@pytest.mark.parametrize("manifest", [
    {"version": "0.3.0", "channel": "other", "release_url": "https://releases.example.test/"},
    {"version": "latest", "channel": "stable", "release_url": "https://releases.example.test/"},
    {"version": "0.3.0", "channel": "stable", "release_url": "file:///update.bat"},
    {"version": "0.3.0", "channel": "stable", "release_url": "http://releases.example.test/"},
    b"invalid json", b" " * 65537, [], {},
], ids=["channel", "version", "file-link", "http-link", "invalid-json", "oversize", "list", "empty"])
def test_invalid_manifest_is_not_offered(manifest):
    assert check_manifest(manifest).status == "error"


def test_http_manifest_rejected_before_network():
    assert check_for_updates({"oneboard_update_enabled": True,
                              "oneboard_update_manifest_url": "http://example.test/"}).status == "error"


def test_version_dialog_exposes_open_source_license_and_upstream():
    app = QApplication.instance() or QApplication([])
    dialog = UpdateDialog({})

    text = dialog.open_source_notice.text()
    assert APP_NAME in text
    assert PROJECT_LICENSE in text
    assert "source code" in text.lower()
    assert "matching Git tag" in text
    assert "LICENSES/LiveTranslate-MIT.txt" in text
    assert "THIRD_PARTY_NOTICES.md" in text
    assert UPSTREAM_PROJECT_NAME in text

    dialog.deleteLater()
    app.processEvents()

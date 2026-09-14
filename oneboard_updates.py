"""Opt-in OneBoard release checks. Never invokes Git or installs downloaded code."""

from dataclasses import dataclass
import json
import re
import threading
from urllib.parse import urlsplit

import httpx
from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QPushButton, QVBoxLayout

from branding import APP_NAME, OPEN_SOURCE_NOTICE
from version import VERSION, UPDATE_CHANNEL, UPDATE_MANIFEST_URL, RELEASE_URL


@dataclass(frozen=True)
class UpdateResult:
    status: str
    message: str
    version: str = ""
    release_url: str = ""


def _version_key(value):
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(?:-(alpha|beta|rc)(\d+))?", value)
    if not match:
        raise ValueError("Unsupported release version")
    major, minor, patch, stage, revision = match.groups()
    return (int(major), int(minor), int(patch),
            {"alpha": 0, "beta": 1, "rc": 2, None: 3}[stage], int(revision or 0))


def _https_url(value):
    try:
        parsed = urlsplit(value)
        return (parsed.scheme == "https" and bool(parsed.hostname)
                and not parsed.username and not parsed.password)
    except (ValueError, TypeError):
        return False


def check_for_updates(settings, *, client_factory=httpx.Client):
    endpoint = settings.get("oneboard_update_manifest_url", UPDATE_MANIFEST_URL)
    channel = settings.get("oneboard_update_channel", UPDATE_CHANNEL)
    if not settings.get("oneboard_update_enabled", False) or not endpoint:
        return UpdateResult("disabled", "Update checks are disabled. No OneBoard release service is configured.")
    if not _https_url(endpoint):
        return UpdateResult("error", "The OneBoard update manifest must use an HTTPS URL.")
    try:
        with client_factory(timeout=5.0, follow_redirects=False) as client:
            with client.stream("GET", endpoint) as response:
                response.raise_for_status()
                chunks = bytearray()
                for chunk in response.iter_bytes():
                    chunks.extend(chunk)
                    if len(chunks) > 65536:
                        raise ValueError("Update manifest is too large")
        manifest = json.loads(chunks)
        if not isinstance(manifest, dict) or manifest.get("channel") != channel:
            raise ValueError("Update channel does not match")
        remote = manifest["version"]
        release = manifest.get("release_url") or settings.get("oneboard_release_url", RELEASE_URL)
        if not _https_url(release):
            raise ValueError("Release link must use HTTPS")
        if _version_key(remote) > _version_key(VERSION):
            return UpdateResult("available", f"OneBoard Live Translate {remote} is available.", remote, release)
        return UpdateResult("current", f"You are using OneBoard Live Translate {VERSION}.", VERSION)
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return UpdateResult("error", "Could not verify the OneBoard release information. Try again later or contact your distributor.")


class UpdateDialog(QDialog):
    result_received = pyqtSignal(object)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = dict(settings)
        self.release_url = ""
        self.setWindowTitle(f"{APP_NAME} — Version and updates")
        self.setMinimumWidth(480)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"{APP_NAME}\nVersion {VERSION}"))
        self.open_source_notice = QLabel(OPEN_SOURCE_NOTICE)
        self.open_source_notice.setWordWrap(True)
        self.open_source_notice.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self.open_source_notice)
        self.status = QLabel("Check for releases from your configured OneBoard distributor.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.check_button = QPushButton("Check for updates")
        self.check_button.clicked.connect(self.check)
        layout.addWidget(self.check_button)
        self.release_button = QPushButton("Open OneBoard release page")
        self.release_button.setEnabled(False)
        self.release_button.clicked.connect(self.open_release)
        layout.addWidget(self.release_button)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.result_received.connect(self.show_result)
        if not settings.get("oneboard_update_enabled", False) or not settings.get("oneboard_update_manifest_url", UPDATE_MANIFEST_URL):
            self.show_result(check_for_updates(settings))
            self.check_button.setEnabled(False)

    def check(self):
        self.check_button.setEnabled(False)
        self.status.setText("Checking OneBoard release information…")
        self._thread = threading.Thread(
            target=lambda: self.result_received.emit(check_for_updates(self.settings)), daemon=True)
        self._thread.start()

    def show_result(self, result):
        self.status.setText(result.message)
        self.release_url = result.release_url
        self.release_button.setEnabled(bool(self.release_url))
        self.check_button.setEnabled(result.status != "disabled")

    def open_release(self):
        if _https_url(self.release_url):
            QDesktopServices.openUrl(QUrl(self.release_url))

"""OneBoard prerequisite checks and user-approved model preparation.

Checks never download models. ASR cache inspection/downloads reuse upstream's
model manager; Ollama is a separate, user-level managed prerequisite.
"""

from dataclasses import dataclass
import importlib
import json
import logging
import os
from pathlib import Path
import platform
import shutil
import subprocess
import threading
import time
from urllib.parse import urlsplit

import httpx
from PyQt6.QtCore import QObject, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QLabel, QMessageBox, QProgressBar,
    QPushButton, QTextEdit, QVBoxLayout, QWidget,
)

from branding import APP_NAME
from oneboard_log_safety import safe_exception_text

OLLAMA_BASE_URL = "http://127.0.0.1:11434"
OLLAMA_DOWNLOAD_URL = "https://ollama.com/download/windows"
DEFAULT_TRANSLATION_MODEL = "qwen3:4b-instruct-2507-q4_K_M"


@dataclass(frozen=True)
class ReadinessItem:
    code: str
    title: str
    state: str
    detail: str
    action: str = ""

    @property
    def blocking(self):
        return self.state in {"missing", "error"}


@dataclass(frozen=True)
class ReadinessReport:
    items: tuple[ReadinessItem, ...]

    @property
    def blocking(self):
        return tuple(item for item in self.items if item.blocking)

    @property
    def ready(self):
        return not self.blocking


def selected_asr(config, settings):
    from model_manager import normalize_asr_engine_selection

    base = config.get("asr", {})
    engine, funasr_model = normalize_asr_engine_selection(
        settings.get("asr_engine", base.get("asr_engine", "whisper")),
        settings.get("funasr_model", base.get("funasr_model")),
    )
    model = (funasr_model if engine == "funasr" else
             settings.get("whisper_model_size", base.get("model_size", "small")))
    return engine, model, settings.get("hub", "hf")


def selected_translation(config, settings):
    models = settings.get("models", [])
    index = settings.get("active_model", 0)
    if models and isinstance(index, int) and 0 <= index < len(models):
        return models[index]
    return config.get("translation", {})


def uses_local_ollama(config, settings):
    """An Advanced OpenAI-compatible endpoint must not require local Ollama."""
    endpoint = selected_translation(config, settings).get("api_base", "")
    try:
        parsed = urlsplit(endpoint)
        return (parsed.scheme == "http" and parsed.hostname in
                {"localhost", "127.0.0.1", "::1"} and parsed.port == 11434)
    except (TypeError, ValueError):
        return False


def find_ollama():
    executable = shutil.which("ollama")
    if executable:
        return executable
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidate = Path(local) / "Programs" / "Ollama" / "ollama.exe"
        if candidate.is_file():
            return str(candidate)
    return None


def start_ollama(executable):
    """Start an installed user-level server hidden, bound only to loopback."""
    environment = os.environ.copy()
    environment["OLLAMA_HOST"] = "127.0.0.1:11434"
    return subprocess.Popen(
        [executable, "serve"], stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        env=environment, close_fds=True,
    )


def ollama_models():
    with httpx.Client(timeout=3.0, trust_env=False) as client:
        response = client.get(f"{OLLAMA_BASE_URL}/api/tags")
        response.raise_for_status()
        payload = response.json()
    models = payload.get("models")
    if not isinstance(models, list):
        raise ValueError("Ollama returned an invalid model list")
    return {str(model.get("name", model.get("model", ""))) for model in models
            if isinstance(model, dict)}


def _audio_check(settings, config):
    from audio_capture import list_input_devices, list_output_devices

    device = settings.get("audio_device", config.get("audio", {}).get("device"))
    mic = settings.get("mic_device")
    selected = []
    missing = []
    if device != "__disabled__":
        outputs = list_output_devices()
        if not outputs or (device and device not in outputs):
            missing.append("selected system audio output")
        else:
            selected.append(device or "Default system audio")
    if mic:
        inputs = list_input_devices()
        if not inputs or (mic != "__default__" and mic not in inputs):
            missing.append("selected microphone")
        else:
            selected.append("Default microphone" if mic == "__default__" else mic)
    if missing or not selected:
        detail = ("Unavailable: " + ", ".join(missing) if missing else
                  "No audio source is enabled.")
        return ReadinessItem("audio", "Audio source", "missing", detail +
                             " Connect a device or choose a source in Advanced.")
    return ReadinessItem("audio", "Audio source", "ready", ", ".join(selected))


def _runtime_check(engine):
    modules = {
        "whisper": ("torch", "faster_whisper", "ctranslate2"),
        "funasr": ("torch", "torchaudio", "funasr"),
        "anime-whisper": ("torch", "transformers"),
        "remote-whisper": ("torch", "httpx"),
    }.get(engine)
    if modules is None:
        return ReadinessItem("asr_runtime", "Speech runtime", "error",
                             "Unknown speech engine. Choose an engine in Advanced.")
    try:
        for module in modules:
            importlib.import_module(module)
    except Exception as exc:
        logging.getLogger(__name__).exception("Selected ASR runtime failed to import")
        return ReadinessItem("asr_runtime", "Speech runtime", "error",
                             f"{engine} could not load ({type(exc).__name__}). "
                             "Repair or reinstall the application runtime; details are in Advanced logs.")
    return ReadinessItem("asr_runtime", "Speech runtime", "ready", engine)


def check_readiness(config, settings, *, start_service=False):
    """Inspect selected prerequisites. Only explicitly requested service start mutates state."""
    from model_manager import is_asr_cached, is_silero_cached

    items = [ReadinessItem("system", "Operating system",
                          "ready" if platform.system() == "Windows" else "error",
                          "Windows audio capture is supported." if platform.system() == "Windows"
                          else "This release requires Windows WASAPI audio capture.")]
    try:
        items.append(_audio_check(settings, config))
    except Exception as exc:
        items.append(ReadinessItem("audio", "Audio source", "error",
                                   f"Audio devices could not be checked ({type(exc).__name__}). "
                                   "Reconnect the device and refresh, or open Advanced."))
    engine, model, hub = selected_asr(config, settings)
    items.append(_runtime_check(engine))
    for code, title, cached in (
        ("vad_model", "Speech activity model", is_silero_cached),
        ("asr_model", "Speech recognition model",
         lambda: is_asr_cached(engine, model, hub)),
    ):
        try:
            present = cached()
            detail = ("Managed by the selected remote speech server." if
                      code == "asr_model" and engine == "remote-whisper" else
                      (f"{engine}: {model}" if code == "asr_model" else "Silero VAD"))
            items.append(ReadinessItem(code, title, "ready" if present else "missing",
                                       detail + (" is available." if present else " needs a download."),
                                       "" if present else "speech"))
        except Exception as exc:
            items.append(ReadinessItem(code, title, "error",
                                       f"Model cache could not be checked ({type(exc).__name__}).", "speech"))
    try:
        torch = importlib.import_module("torch")
        gpu = torch.cuda.is_available()
        selected_device = settings.get("asr_device", config.get("asr", {}).get("device", "cpu"))
        using_cpu = selected_device == "cpu" or not gpu
        items.append(ReadinessItem("gpu", "Performance", "advisory" if using_cpu else "ready",
                                   "CPU mode is supported. Recognition may be slower and CPU use may be high."
                                   if using_cpu else "CUDA GPU is available."))
    except Exception:
        items.append(ReadinessItem("gpu", "Performance", "advisory",
                                   "GPU availability could not be checked. GPU advice does not block setup."))

    if not uses_local_ollama(config, settings):
        items.append(ReadinessItem("translation_service", "Translation engine", "advisory",
                                   "An Advanced translation service is selected. Its connection is checked "
                                   "when translating; local Ollama is optional."))
        return ReadinessReport(tuple(items))

    executable = find_ollama()
    names = None
    try:
        names = ollama_models()
    except Exception:
        if start_service and executable:
            try:
                process = start_ollama(executable)
                for _ in range(5):
                    time.sleep(0.5)
                    try:
                        names = ollama_models()
                        break
                    except Exception:
                        if process.poll() is not None:
                            break
            except OSError:
                pass
    # A reachable API is sufficient (portable/WSL servers need no local CLI).
    items.append(ReadinessItem("ollama_install", "Ollama installation",
                               "ready" if executable or names is not None else "missing",
                               "Ollama is available." if executable or names is not None else
                               "Install Ollama using its official Windows installer, then refresh.",
                               "" if executable or names is not None else "install_ollama"))
    items.append(ReadinessItem("ollama_service", "Translation service",
                               "ready" if names is not None else "missing",
                               "Ollama is responding on localhost:11434." if names is not None else
                               "Ollama is not responding. Start it and refresh.",
                               "" if names is not None else "start_ollama"))
    required = selected_translation(config, settings).get("model", DEFAULT_TRANSLATION_MODEL)
    available = names is not None and (required in names or
                                      (":" not in required and f"{required}:latest" in names))
    items.append(ReadinessItem("translation_model", "Translation model",
                               "ready" if available else "missing",
                               f"{required} " + ("is available." if available else "needs a download."),
                               "" if available else "pull_model"))
    return ReadinessReport(tuple(items))


class PullCancelled(Exception):
    """User cancelled an approved download."""


def pull_ollama_model(model, progress, cancel, *, client_factory=httpx.Client):
    """Stream an approved pull; fail on interrupted/error streams, including HTTP 200 errors."""
    if not isinstance(model, str) or not model.strip():
        raise ValueError("Select a translation model first.")
    deadline = time.monotonic() + 4 * 60 * 60
    if cancel.is_set():
        raise PullCancelled()
    with client_factory(timeout=httpx.Timeout(15.0, connect=5.0), trust_env=False) as client:
        with client.stream("POST", f"{OLLAMA_BASE_URL}/api/pull",
                           json={"model": model, "stream": True}) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if cancel.is_set():
                    raise PullCancelled()
                if time.monotonic() > deadline:
                    raise TimeoutError("Model download exceeded four hours. Retry to resume.")
                if not line:
                    continue
                payload = json.loads(line)
                if not isinstance(payload, dict):
                    raise ValueError("Ollama returned invalid download progress.")
                if payload.get("error"):
                    raise RuntimeError(str(payload["error"]))
                progress(payload)
                if payload.get("status") == "success":
                    return
    if cancel.is_set():
        raise PullCancelled()
    raise RuntimeError("Download ended before completion. Refresh or retry to resume.")


class _TaskSignals(QObject):
    completed = pyqtSignal(object)
    failed = pyqtSignal(str)
    progress = pyqtSignal(object)


class ReadinessPanel(QWidget):
    """Reusable asynchronous checks and repair actions for setup and Start."""

    report_ready = pyqtSignal(object)

    def __init__(self, config, settings, parent=None, codes=None):
        super().__init__(parent)
        self.config = config
        self.settings = settings
        self.codes = set(codes) if codes else None
        self.report = None
        self._busy = False
        self._cancel = threading.Event()
        self._signals = _TaskSignals(self)
        self._signals.completed.connect(self._finished)
        self._signals.failed.connect(self._failed)
        self._signals.progress.connect(self._progress)
        layout = QVBoxLayout(self)
        self.results = QTextEdit()
        self.results.setReadOnly(True)
        self.results.setMinimumHeight(180)
        layout.addWidget(self.results)
        self.status = QLabel("Check the selected audio, speech and translation prerequisites.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.hide()
        layout.addWidget(self.progress)
        self.refresh_button = QPushButton("Check again")
        self.refresh_button.clicked.connect(lambda: self.refresh())
        layout.addWidget(self.refresh_button)
        self.buttons = {}
        for action, label, callback in (
            ("speech", "Download speech models…", self.download_speech),
            ("install_ollama", "Open official Ollama installer page", self.install_ollama),
            ("start_ollama", "Start Ollama and check again", lambda: self.refresh(start_service=True)),
            ("pull_model", "Download translation model…", self.download_translation),
        ):
            button = QPushButton(label)
            button.clicked.connect(callback)
            button.hide()
            layout.addWidget(button)
            self.buttons[action] = button
        self.cancel_button = QPushButton("Cancel download")
        self.cancel_button.clicked.connect(self.cancel_download)
        self.cancel_button.hide()
        layout.addWidget(self.cancel_button)

    def _run(self, operation, *, download=False):
        if self._busy:
            return
        self._busy = True
        self._cancel.clear()
        self.refresh_button.setEnabled(False)
        for button in self.buttons.values():
            button.setEnabled(False)
        self.cancel_button.setVisible(download)
        self.cancel_button.setEnabled(True)
        self.progress.setVisible(download)
        self.progress.setRange(0, 0)

        def worker():
            try:
                result = operation()
                self._signals.completed.emit(result)
            except PullCancelled:
                self._safe_failure("Download cancelled. Existing download data can be resumed by retrying.")
            except Exception as exc:
                self._safe_failure(
                    f"{type(exc).__name__}: {safe_exception_text(exc)}"
                )

        threading.Thread(target=worker, daemon=True, name="OneBoardReadiness").start()

    def _safe_failure(self, message):
        try:
            self._signals.failed.emit(message)
        except RuntimeError:
            pass  # The window was closed while a bounded network operation finished.

    def _reset_busy(self):
        self._busy = False
        self.refresh_button.setEnabled(True)
        self.cancel_button.hide()
        self.progress.hide()
        for button in self.buttons.values():
            button.setEnabled(True)

    def _finished(self, result):
        self._reset_busy()
        if not isinstance(result, ReadinessReport):
            self.refresh()
            return
        self.report = result
        visible = [item for item in result.items if not self.codes or item.code in self.codes]
        self.results.setPlainText("\n\n".join(
            f"{item.title} — {item.state.upper()}\n{item.detail}" for item in visible))
        for action, button in self.buttons.items():
            button.setVisible(any(item.action == action for item in visible))
        service_ok = any(item.code == "ollama_service" and item.state == "ready"
                         for item in result.items)
        self.buttons["pull_model"].setEnabled(service_ok)
        self.status.setText("Ready. You can begin translating." if result.ready else
                            "Some prerequisites need attention. You can still open Advanced settings.")
        self.report_ready.emit(result)

    def _failed(self, message):
        self._reset_busy()
        self.status.setText(message)

    def _progress(self, payload):
        self.status.setText(str(payload.get("status", "Downloading…")))
        total = payload.get("total", 0)
        completed = payload.get("completed", 0)
        if isinstance(total, (int, float)) and total > 0 and isinstance(completed, (int, float)):
            self.progress.setRange(0, 100)
            self.progress.setValue(min(100, max(0, int(100 * completed / total))))
            self.status.setText(f"{payload.get('status', 'Downloading')} — "
                                f"{completed / 1024**3:.2f} / {total / 1024**3:.2f} GB")

    def refresh(self, *, start_service=False):
        if not self._busy:
            self.report = None
            self.status.setText("Checking prerequisites…")
            self._run(lambda: check_readiness(self.config, self.settings, start_service=start_service))

    def install_ollama(self):
        QDesktopServices.openUrl(QUrl(OLLAMA_DOWNLOAD_URL))
        self.status.setText("Use the official Windows installer. It may request Windows approval. "
                            "Return here and check again after installation.")

    def download_speech(self):
        from dialogs import ModelDownloadDialog
        from model_manager import format_size, get_missing_models

        engine, model, hub = selected_asr(self.config, self.settings)
        missing = get_missing_models(engine, model, hub)
        if not missing:
            self.status.setText("No downloadable speech models are missing. "
                                "For a custom model, choose a valid local model folder in Advanced.")
            return
        names = ", ".join(item["name"] for item in missing)
        size = format_size(sum(item.get("estimated_bytes", 0) for item in missing))
        answer = QMessageBox.question(self, "Download speech models",
                                      f"Download {names} (approximately {size})? "
                                      "This uses your internet connection and local disk space.",
                                      QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                      QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        dialog = ModelDownloadDialog(missing, hub=hub,
                                     proxy=self.settings.get("download_proxy", "system"), parent=self)
        dialog.exec()
        self.refresh()

    def download_translation(self):
        model = selected_translation(self.config, self.settings).get("model", DEFAULT_TRANSLATION_MODEL)
        answer = QMessageBox.question(self, "Download translation model",
                                      f"Download {model} through Ollama? Model downloads can use several "
                                      "GB of internet data and disk space. Download now?",
                                      QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                      QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.report = None
        self.status.setText("Starting approved model download…")
        self._run(lambda: pull_ollama_model(model, self._signals.progress.emit, self._cancel), download=True)

    def cancel_download(self):
        self._cancel.set()
        self.cancel_button.setEnabled(False)
        self.status.setText("Cancelling… this may take up to 15 seconds while a network read finishes.")


class ReadinessDialog(QDialog):
    def __init__(self, config, settings, parent=None, *, start_service=False):
        super().__init__(parent)
        self.setWindowTitle(f"{APP_NAME} — Readiness")
        self.resize(620, 660)
        layout = QVBoxLayout(self)
        self.panel = ReadinessPanel(config, settings, self)
        layout.addWidget(self.panel)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                   QDialogButtonBox.StandardButton.Cancel)
        self.continue_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.continue_button.setText("Continue")
        self.continue_button.setEnabled(False)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.panel.report_ready.connect(lambda report: self.continue_button.setEnabled(report.ready))
        QTimer.singleShot(0, lambda: self.panel.refresh(start_service=start_service))

    @property
    def report(self):
        return self.panel.report

    def accept(self):
        if self.report and self.report.ready and not self.panel._busy:
            super().accept()

    def reject(self):
        self.panel._cancel.set()
        super().reject()

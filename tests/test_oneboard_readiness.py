import json
import os
from types import SimpleNamespace
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import httpx
import pytest
from PyQt6.QtWidgets import QApplication, QMessageBox

import model_manager
import oneboard_readiness as readiness


@pytest.fixture
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def config():
    return {"audio": {"device": None},
            "asr": {"asr_engine": "whisper", "model_size": "small", "device": "cpu"},
            "translation": {"api_base": "http://localhost:11434/v1",
                            "model": readiness.DEFAULT_TRANSLATION_MODEL}}


@pytest.fixture
def ready_environment(monkeypatch):
    monkeypatch.setattr(readiness.platform, "system", lambda: "Windows")
    monkeypatch.setattr(readiness, "_audio_check", lambda settings, config:
                        readiness.ReadinessItem("audio", "Audio", "ready", "Output"))
    monkeypatch.setattr(readiness, "_runtime_check", lambda engine:
                        readiness.ReadinessItem("asr_runtime", "Runtime", "ready", engine))
    monkeypatch.setattr(readiness.importlib, "import_module", lambda name:
                        SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False)))
    monkeypatch.setattr(model_manager, "is_silero_cached", lambda: True)
    monkeypatch.setattr(model_manager, "is_asr_cached", lambda *args: True)
    monkeypatch.setattr(readiness, "find_ollama", lambda: "ollama.exe")
    monkeypatch.setattr(readiness, "ollama_models", lambda: {readiness.DEFAULT_TRANSLATION_MODEL})


def test_cpu_is_advisory_and_checks_never_download(config, ready_environment, monkeypatch):
    monkeypatch.setattr(model_manager, "download_asr", lambda *a, **kw: pytest.fail("silent download"))
    monkeypatch.setattr(readiness, "start_ollama", lambda *a: pytest.fail("silent start"))
    report = readiness.check_readiness(config, {})
    assert report.ready
    assert next(item for item in report.items if item.code == "gpu").state == "advisory"


def test_selected_model_missing_blocks_start(config, ready_environment, monkeypatch):
    calls = []
    monkeypatch.setattr(model_manager, "is_asr_cached", lambda *args: calls.append(args) or False)
    report = readiness.check_readiness(config, {"whisper_model_size": "large-v3", "hub": "ms"})
    assert calls == [("whisper", "large-v3", "ms")]
    assert {item.code for item in report.blocking} == {"asr_model"}


def test_silero_missing_is_actionable(config, ready_environment, monkeypatch):
    monkeypatch.setattr(model_manager, "is_silero_cached", lambda: False)
    report = readiness.check_readiness(config, {})
    assert report.blocking[0].code == "vad_model"
    assert report.blocking[0].action == "speech"


def test_advanced_translation_does_not_require_ollama(config, ready_environment, monkeypatch):
    monkeypatch.setattr(readiness, "find_ollama", lambda: pytest.fail("Must not inspect Ollama"))
    settings = {"models": [{"api_base": "https://example.invalid/v1", "model": "custom"}],
                "active_model": 0, "asr_engine": "remote-whisper"}
    report = readiness.check_readiness(config, settings)
    assert report.ready
    assert "ollama_service" not in {item.code for item in report.items}


def test_api_available_without_cli_is_ready(config, ready_environment, monkeypatch):
    monkeypatch.setattr(readiness, "find_ollama", lambda: None)
    assert readiness.check_readiness(config, {}).ready


def test_installed_but_stopped_is_actionable(config, ready_environment, monkeypatch):
    monkeypatch.setattr(readiness, "ollama_models", lambda: (_ for _ in ()).throw(OSError()))
    report = readiness.check_readiness(config, {})
    assert {item.code for item in report.blocking} == {"ollama_service", "translation_model"}


def test_explicit_service_start_and_recheck(config, ready_environment, monkeypatch):
    calls = []

    def models():
        if not calls:
            raise OSError()
        return {readiness.DEFAULT_TRANSLATION_MODEL}

    monkeypatch.setattr(readiness, "ollama_models", models)
    monkeypatch.setattr(readiness.time, "sleep", lambda _: None)
    monkeypatch.setattr(readiness, "start_ollama", lambda path: calls.append(path))
    assert readiness.check_readiness(config, {}, start_service=True).ready
    assert calls == ["ollama.exe"]


def test_safe_hidden_user_level_start(monkeypatch):
    calls = []
    monkeypatch.setattr(readiness.subprocess, "Popen", lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr(readiness.subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False)
    readiness.start_ollama("C:/Programs/Ollama/ollama.exe")
    args, options = calls[0]
    assert args == (["C:/Programs/Ollama/ollama.exe", "serve"],)
    assert options["creationflags"] == 0x08000000
    assert options["env"]["OLLAMA_HOST"] == "127.0.0.1:11434"
    assert "shell" not in options


@pytest.mark.parametrize("audio,mic,outputs,inputs,blocked", [
    (None, None, ["Speakers"], [], False),
    ("Removed", None, ["Speakers"], [], True),
    ("__disabled__", None, ["Speakers"], [], True),
    ("__disabled__", "__default__", [], ["Mic"], False),
    (None, "Removed", ["Speakers"], ["Mic"], True),
    (None, None, [], [], True),
])
def test_selected_audio_sources(config, monkeypatch, audio, mic, outputs, inputs, blocked):
    import audio_capture

    monkeypatch.setattr(audio_capture, "list_output_devices", lambda: outputs)
    monkeypatch.setattr(audio_capture, "list_input_devices", lambda: inputs)
    item = readiness._audio_check({"audio_device": audio, "mic_device": mic}, config)
    assert item.blocking is blocked


def _pull_client(events, requests):
    def handler(request):
        requests.append(request)
        return httpx.Response(200, text="\n".join(json.dumps(event) for event in events))

    return lambda **kwargs: httpx.Client(transport=httpx.MockTransport(handler), **kwargs)


def test_pull_stream_updates_progress_and_requires_success():
    requests, progress = [], []
    readiness.pull_ollama_model("qwen:test", progress.append, threading.Event(),
                                client_factory=_pull_client([
                                    {"status": "pulling", "total": 100, "completed": 50},
                                    {"status": "success"}], requests))
    assert progress[0]["completed"] == 50
    assert json.loads(requests[0].content) == {"model": "qwen:test", "stream": True}
    assert requests[0].url.path == "/api/pull"


@pytest.mark.parametrize("events,error", [
    ([{"error": "disk full"}], "disk full"),
    ([{"status": "pulling"}], "before completion"),
])
def test_pull_failure_in_http_200_is_not_success(events, error):
    with pytest.raises(RuntimeError, match=error):
        readiness.pull_ollama_model("qwen:test", lambda _: None, threading.Event(),
                                    client_factory=_pull_client(events, []))


def test_pull_cancellation_stops_between_progress_events():
    cancel = threading.Event()
    with pytest.raises(readiness.PullCancelled):
        readiness.pull_ollama_model("qwen:test", lambda _: cancel.set(), cancel,
                                    client_factory=_pull_client([
                                        {"status": "pulling"}, {"status": "success"}], []))


def test_pull_timeout_is_reported():
    def handler(request):
        raise httpx.ReadTimeout("No progress")

    with pytest.raises(httpx.ReadTimeout):
        readiness.pull_ollama_model("qwen:test", lambda _: None, threading.Event(),
                                    client_factory=lambda **kwargs: httpx.Client(
                                        transport=httpx.MockTransport(handler), **kwargs))


def test_gui_download_declined_performs_no_work(qapp, config, monkeypatch):
    panel = readiness.ReadinessPanel(config, {})
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.No)
    monkeypatch.setattr(panel, "_run", lambda *args, **kwargs: pytest.fail("Download without approval"))
    panel.download_translation()
    panel.close()


def test_gui_cancel_can_be_retried(qapp, config):
    panel = readiness.ReadinessPanel(config, {})
    panel.cancel_download()
    assert panel._cancel.is_set()
    panel._reset_busy()
    panel._finished(readiness.ReadinessReport((readiness.ReadinessItem(
        "translation_model", "Translation", "missing", "Missing", "pull_model"),)))
    assert not panel.buttons["pull_model"].isEnabled()
    panel.close()


def test_gui_missing_model_blocks_continue(qapp, config):
    dialog = readiness.ReadinessDialog(config, {})
    dialog.panel._finished(readiness.ReadinessReport((readiness.ReadinessItem(
        "asr_model", "Speech", "missing", "Missing", "speech"),)))
    assert not dialog.continue_button.isEnabled()
    dialog.panel._finished(readiness.ReadinessReport(()))
    assert dialog.continue_button.isEnabled()
    dialog.reject()

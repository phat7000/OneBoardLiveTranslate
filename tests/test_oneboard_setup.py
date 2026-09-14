import os
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PyQt6.QtWidgets import QApplication, QMessageBox

import oneboard_setup as setup
from oneboard_readiness import DEFAULT_TRANSLATION_MODEL, ReadinessItem, ReadinessReport


@pytest.fixture
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def config():
    return {"asr": {"asr_engine": "whisper", "model_size": "small"},
            "translation": {"api_base": "http://localhost:11434/v1", "model": DEFAULT_TRANSLATION_MODEL}}


def test_first_run_state():
    assert setup.first_run_required(None)
    assert setup.first_run_required({"ui_language": "en"})
    assert not setup.first_run_required({"oneboard_setup_completed": True})


def test_finish_persists_completion_and_audio_in_mutable_normal_settings(qapp, config):
    saved = []
    settings = {"asr_engine": "whisper", "oneboard_setup_completed": False, "other": 42}
    wizard = setup.SetupWizard(config, settings, saved.append)
    assert len(wizard.pageIds()) == 7
    wizard.working_settings["audio_device"] = "Speakers"
    wizard.accept()
    assert settings["oneboard_setup_completed"] is True
    assert settings["audio_device"] == "Speakers"
    assert settings["other"] == 42
    assert saved == [settings]


def test_cancel_does_not_mark_setup_done_or_save_audio(qapp, config):
    settings, saved = {}, []
    wizard = setup.SetupWizard(config, settings, saved.append)
    wizard.working_settings["audio_device"] = "Speakers"
    wizard.reject()
    assert settings == {}
    assert saved == []


def test_reopen_preserves_advanced_model_and_settings(qapp, config):
    settings = {"oneboard_setup_completed": True, "asr_engine": "funasr",
                "funasr_model": "sensevoice-small", "models": [
                    {"api_base": "https://example.invalid/v1", "model": "custom"}], "active_model": 0}
    wizard = setup.SetupWizard(config, settings, lambda _: None)
    wizard.accept()
    assert settings["asr_engine"] == "funasr"
    assert settings["models"][0]["model"] == "custom"


def test_missing_models_can_be_postponed_without_claiming_readiness(qapp, config):
    settings = {}
    wizard = setup.SetupWizard(config, settings, lambda _: None)
    report = ReadinessReport((ReadinessItem("asr_model", "Speech model", "missing", "Download needed"),))
    wizard.complete_page.checks._finished(report)
    assert "MISSING" in wizard.complete_page.checks.results.toPlainText()
    wizard.accept()
    assert settings["oneboard_setup_completed"] is True
    assert not wizard.complete_page.checks.report.ready


def test_save_failure_does_not_mark_setup_complete(qapp, config, monkeypatch):
    settings, messages = {}, []

    def fail(_):
        raise OSError("not writable")

    monkeypatch.setattr(QMessageBox, "critical", lambda *args: messages.append(args))
    wizard = setup.SetupWizard(config, settings, fail)
    wizard.accept()
    assert settings == {}
    assert messages
    wizard.reject()


def test_reported_save_failure_does_not_mark_setup_complete(qapp, config, monkeypatch):
    settings, messages = {}, []
    monkeypatch.setattr(QMessageBox, "critical", lambda *args: messages.append(args))
    wizard = setup.SetupWizard(config, settings, lambda _: False)
    wizard.accept()
    assert settings == {}
    assert messages
    wizard.reject()


def test_settings_writer_reports_success_and_failure(tmp_path, monkeypatch):
    import control_panel

    destination = tmp_path / "settings.json"
    monkeypatch.setattr(control_panel, "SETTINGS_FILE", destination)
    assert control_panel._save_settings({"saved": True}) is True
    assert destination.read_text(encoding="utf-8")

    monkeypatch.setattr(
        control_panel, "SETTINGS_FILE", tmp_path / "missing-parent" / "settings.json",
    )
    assert control_panel._save_settings({"saved": False}) is False


def test_audio_test_captures_levels_and_always_stops(monkeypatch):
    import audio_capture

    events, levels = [], []
    cancel = threading.Event()

    class Capture:
        def __init__(self, **kwargs):
            events.append(kwargs)

        def set_mic_device(self, device):
            events.append(device)

        def start(self):
            events.append("start")

        def get_audio(self, **kwargs):
            cancel.set()
            return np.array([0.2, -0.2], dtype=np.float32), 0.1

        def stop(self):
            events.append("stop")

    monkeypatch.setattr(audio_capture, "AudioCapture", Capture)
    peak = setup.test_audio_source({"audio_device": "Speakers", "mic_device": None}, levels.append, cancel)
    assert peak == pytest.approx(0.2)
    assert levels == [100]
    assert events == [{"device": "Speakers"}, None, "start", "stop"]


def test_audio_test_stops_after_start_failure(monkeypatch):
    import audio_capture

    stopped = []

    class Capture:
        def __init__(self, **kwargs):
            pass

        def set_mic_device(self, device):
            pass

        def start(self):
            raise OSError("device unavailable")

        def stop(self):
            stopped.append(True)

    monkeypatch.setattr(audio_capture, "AudioCapture", Capture)
    with pytest.raises(OSError):
        setup.test_audio_source({}, lambda _: None, threading.Event())
    assert stopped == [True]

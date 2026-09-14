"""Exercise real Qt product/control-panel integration with a fake audio pipeline."""

import os
import threading
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
import yaml
import oneboard_app
from PyQt6.QtWidgets import QApplication, QPushButton
from oneboard_presets import fresh_settings
from oneboard_readiness import ReadinessItem, ReadinessReport


class FakePipeline:
    def __init__(self, config):
        self._running = False
        self._asr_ready = False
        self._mem_periodic_timer = None
        self._msg_id = 0
        self.starts = self.stops = 0

    def set_overlay(self, overlay):
        self.overlay = overlay

    def set_subtitle_window(self, window):
        pass

    def _on_settings_changed(self, settings):
        self.settings = settings
        self._asr_ready = self.allow_model_load

    def _on_target_language_changed(self, target):
        self.target = target

    def _on_model_changed(self, model):
        self.model = model

    def start(self):
        self._running = True
        self.starts += 1

    def stop(self):
        self._running = self._asr_ready = False
        self.stops += 1


@pytest.fixture
def controller(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([])
    import control_panel
    import dialogs
    import audio_capture
    monkeypatch.setattr(control_panel, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr(control_panel, "_save_settings", lambda value: None)
    monkeypatch.setattr(dialogs, "_save_settings", lambda value: None)
    monkeypatch.setattr(oneboard_app, "list_output_devices", lambda: ["Speakers"])
    monkeypatch.setattr(audio_capture, "list_output_devices", lambda: ["Speakers"])
    monkeypatch.setattr(audio_capture, "list_input_devices", lambda: ["Microphone"])
    config = yaml.safe_load(Path("config.yaml").read_text(encoding="utf-8"))
    saved = []
    obj = oneboard_app.OneBoardController(
        config, fresh_settings(config), pipeline_factory=FakePipeline,
        save_settings=lambda value: saved.append(dict(value)),
        readiness_check=lambda config, settings: ReadinessReport(()),
    )
    obj.saved_for_test = saved
    obj.show_windows()
    app.processEvents()
    yield obj
    obj._audio_timer.stop()
    obj._window_save_timer.stop()
    if obj._stopping:
        obj._stop_thread.join(2)
    obj.window.hide()
    obj.display_window.hide()
    obj.panel.hide()
    obj.overlay.hide()
    obj.subwin.hide()
    obj.logs.hide()
    import logging
    logging.getLogger().removeHandler(obj._log_handler)
    obj.deleteLater()
    app.processEvents()


def test_customer_startup_is_idle_and_gear_opens_full_panel(controller):
    assert controller.pipeline is None
    assert controller.window.isVisible()
    assert controller.display_window.isVisible()
    assert not controller.overlay.isVisible()
    controller.window.settings_button.click()
    assert controller.panel.isVisible()
    assert controller.panel._asr_lang.findData("vi") >= 0
    assert controller.panel._asr_lang.findData("ja") >= 0
    assert any(button.text() == "System readiness"
               for button in controller.panel.findChildren(QPushButton))
    assert any(button.text() == "Version and updates"
               for button in controller.panel.findChildren(QPushButton))


def test_display_close_keeps_app_alive_and_control_reopens_same_history(controller):
    app = QApplication.instance()
    controller.source_received(1, "12:00", "Keep this text.", "en", 10)
    app.processEvents()
    controller.display_window.transcript.flush()
    display = controller.display_window

    display.close()
    app.processEvents()
    assert controller.window.isVisible()
    assert not display.isVisible()
    assert not controller._quitting
    assert display.transcript.history.text("source") == "Keep this text."

    controller.window.display_button.click()
    assert controller.display_window is display
    assert display.isVisible()
    assert display.transcript.history.text("source") == "Keep this text."


def test_display_reopen_preserves_maximized_state(controller):
    app = QApplication.instance()
    display = controller.display_window
    display.showMaximized()
    app.processEvents()
    assert display.isMaximized()
    display.close()
    app.processEvents()
    assert not display.isVisible()

    controller.show_display()
    app.processEvents()
    assert display.isVisible()
    assert display.isMaximized()


def test_display_reopen_recovers_from_a_removed_screen(controller):
    app = QApplication.instance()
    screen = QApplication.primaryScreen().availableGeometry()
    display = controller.display_window
    display.close()
    display.setGeometry(
        screen.right() + 10_000,
        screen.bottom() + 10_000,
        display.minimumWidth(),
        display.minimumHeight(),
    )

    controller.show_display()
    app.processEvents()
    assert display.isVisible()
    assert oneboard_app._screen_for_geometry(display.geometry()) is not None


def test_control_close_requests_whole_application_shutdown(controller, monkeypatch):
    requested = []
    monkeypatch.setattr(QApplication.instance(), "quit", lambda: requested.append(True))
    controller.window.close()
    assert requested == [True]
    assert controller._quitting
    assert controller.window.isVisible()  # close is deferred until pipeline cleanup


def test_advanced_style_changes_apply_to_display_window(controller):
    panel = controller.panel
    panel._bg_color_btn.setProperty("hex_color", "#102030")
    panel._header_color_btn.setProperty("hex_color", "#405060")
    panel._orig_color_btn.setProperty("hex_color", "#708090")
    panel._trans_color_btn.setProperty("hex_color", "#a0b0c0")
    panel._ts_color_btn.setProperty("hex_color", "#d0e0f0")
    panel._orig_font_size.setValue(16)
    panel._trans_font_size.setValue(20)
    panel._window_opacity.setValue(82)
    deadline = time.monotonic() + 1
    while panel._save_timer.isActive() and time.monotonic() < deadline:
        QApplication.instance().processEvents()
        time.sleep(0.01)
    assert not panel._save_timer.isActive()

    display = controller.display_window
    assert display._style == panel.get_settings()["style"]
    assert display.transcript.source_edit.font().pointSize() == 16
    assert display.transcript.translation_edit.font().pointSize() == 20
    assert "#708090" in display.transcript.source_edit.styleSheet()
    assert "#a0b0c0" in display.transcript.translation_edit.styleSheet()
    assert display.windowOpacity() == pytest.approx(0.82, abs=1 / 255)


def test_control_start_stop_button_drives_the_pipeline(controller):
    app = QApplication.instance()
    controller.window.start_stop_button.click()
    assert controller.pipeline._running
    assert controller.window.start_stop_button.text() == "Stop"
    controller.window.start_stop_button.click()
    controller._stop_thread.join(2)
    app.processEvents()
    assert not controller.pipeline._running
    assert controller.window.start_stop_button.text() == "Start"


def test_product_window_geometry_is_saved_and_reset_from_advanced(controller):
    screen = QApplication.primaryScreen().availableGeometry()
    controller.window.setGeometry(screen.left() + 10, screen.top() + 10, 500, 230)
    controller.display_window.setGeometry(
        screen.left() + 40,
        screen.top() + 70,
        max(540, min(760, screen.width() - 80)),
        max(420, min(600, screen.height() - 100)),
    )
    controller._save_window_geometries()
    saved = controller.saved_for_test[-1][oneboard_app.WINDOW_STATE_KEY]
    assert saved["control"] == oneboard_app._geometry_state(controller.window)
    assert saved["display"] == oneboard_app._geometry_state(controller.display_window)

    controller.window.move(screen.right() - 200, screen.bottom() - 100)
    controller.display_window.move(screen.left(), screen.top())
    controller._restore_product_windows({oneboard_app.WINDOW_STATE_KEY: saved})
    assert oneboard_app._geometry_state(controller.window) == saved["control"]
    assert oneboard_app._geometry_state(controller.display_window) == saved["display"]

    before = controller.window.geometry()
    assert not oneboard_app._restore_geometry(controller.window, {
        "x": 10**100,
        "y": 10**100,
        "width": 10**100,
        "height": 10**100,
    })
    assert controller.window.geometry() == before
    assert not oneboard_app._restore_geometry(controller.window, {
        "x": screen.right() + 10_000,
        "y": screen.bottom() + 10_000,
        "width": 500,
        "height": 230,
    })
    assert controller.window.geometry() == before
    assert not oneboard_app._restore_geometry(controller.window, {
        "x": float("inf"),
        "y": 0,
        "width": 500,
        "height": 230,
    })
    assert controller.window.geometry() == before

    partly_above = {
        "x": screen.left() + 20,
        "y": screen.top() - 46,
        "width": 500,
        "height": 230,
    }
    assert oneboard_app._restore_geometry(controller.window, partly_above)
    assert controller.window.geometry().top() == screen.top()

    controller.panel.reset_positions.emit()
    reset = controller.saved_for_test[-1]
    assert reset[oneboard_app.WINDOW_STATE_KEY]["control"] == oneboard_app._geometry_state(controller.window)
    assert reset[oneboard_app.WINDOW_STATE_KEY]["display"] == oneboard_app._geometry_state(controller.display_window)
    assert controller.window.pos() != controller.display_window.pos()
    assert reset["subtitle_mode"]["window_x"] == controller.subwin.x()
    assert reset["overlay_x"] == controller.overlay.x()


def test_missing_readiness_blocks_pipeline_until_user_repairs_it(controller):
    missing = ReadinessReport((ReadinessItem(
        "translation_model", "Translation model", "missing", "Download the selected model."),))

    class CancelledDialog:
        report = missing

        def __init__(self, *args, **kwargs):
            pass

        def exec(self):
            return 0

    controller.readiness_check = lambda config, settings: missing
    controller.readiness_dialog_factory = CancelledDialog
    controller.start()
    assert controller.pipeline is None
    assert controller.window.status_label.text() == "Error · Download the selected model."


def test_setup_can_be_reopened_and_updates_normal_audio_settings(controller):
    calls = []

    class FinishedSetup:
        def __init__(self, config, settings, save, parent=None):
            calls.append((config, settings, save, parent))
            settings.update(audio_device="Speakers", mic_device="__default__",
                            oneboard_setup_completed=True)

        def exec(self):
            return 1

    controller.setup_factory = FinishedSetup
    controller.show_setup()
    assert calls[0][3] is controller.panel
    assert controller.panel.get_settings()["oneboard_setup_completed"] is True
    assert controller.panel._audio_device.currentText() == "Speakers"
    assert controller.panel._mic_device.currentIndex() == 1
    assert controller.window.audio_combo.currentData() == "Speakers"


def test_setup_cannot_open_while_pipeline_owns_audio(controller, monkeypatch):
    messages = []
    monkeypatch.setattr(oneboard_app.QMessageBox, "information",
                        lambda *args: messages.append(args))
    controller.start()
    controller.setup_factory = lambda *args, **kwargs: pytest.fail(
        "Setup opened while live audio was running")
    controller.show_setup()
    assert messages
    assert controller.pipeline._running


def test_presets_sync_advanced_and_save_without_loading_models(controller):
    controller.set_direction("vi-en")
    settings = controller.panel.get_settings()
    assert (settings["asr_language"], settings["source_language"], settings["target_language"]) == ("vi", "vi", "en")
    assert controller.panel._asr_lang.currentData() == "vi"
    assert controller.pipeline is None
    controller.window.swap_button.click()
    assert controller.panel.get_settings()["asr_language"] == "en"
    assert controller.saved_for_test[-1]["target_language"] == "vi"


def test_start_stop_restart_keeps_history_and_uses_settings(controller):
    app = QApplication.instance()
    controller.start()
    assert controller.pipeline._running
    assert controller.pipeline.target == "vi"
    controller.pipeline._msg_id = 1
    controller.overlay.add_message(1, "12:00", "Hello.", "en", 10)
    controller.overlay.update_streaming(1, "Xin")
    controller.overlay.update_translation(1, "Xin chào.", 20)
    app.processEvents()
    controller.display_window.transcript.flush()
    assert controller.display_window.transcript.history.text("translation") == "Xin chào."
    controller.stop()
    deadline = time.monotonic() + 3
    while controller._stopping and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    assert not controller._stopping
    assert not controller.pipeline._running
    controller.start()
    assert controller.pipeline.starts == 2
    assert controller.pipeline.stops == 1
    assert controller.display_window.transcript.history.text("source") == "Hello."


def test_start_error_status_redacts_credential(controller):
    sentinel = "credential-value-that-must-not-be-displayed"

    class FailingPipeline(FakePipeline):
        def start(self):
            raise RuntimeError(f"API key: {sentinel}")

    controller.pipeline_factory = FailingPipeline
    controller.start()

    assert sentinel not in controller._error
    assert sentinel not in controller.window.status_label.text()
    assert "<redacted>" in controller.window.status_label.text()


def test_clear_discards_late_streams(controller):
    controller.start()
    controller.pipeline._msg_id = 3
    controller.source_received(3, "12:00", "Old.", "en", 10)
    controller.clear()
    controller.translation_received(3, "Late.", 10)
    QApplication.instance().processEvents()
    controller.display_window.transcript.flush()
    assert not controller.display_window.transcript.history.text("source")
    assert not controller.display_window.transcript.history.text("translation")
    assert controller.window.status_label.text() == "Listening"


def test_clear_actions_keep_primary_and_advanced_histories_in_sync(controller):
    controller.source_received(1, "12:00", "Primary.", "en", 10)
    controller.overlay.add_message(1, "12:00", "Advanced.", "en", 10)
    QApplication.instance().processEvents()
    assert controller.overlay._messages

    controller.window.clear_button.click()
    QApplication.instance().processEvents()
    assert not controller.display_window.transcript.history.segments
    assert not controller.overlay._messages

    controller.source_received(2, "12:01", "Primary again.", "en", 10)
    controller.overlay.add_message(2, "12:01", "Advanced again.", "en", 10)
    QApplication.instance().processEvents()
    controller.overlay._handle.clear_clicked.emit()
    QApplication.instance().processEvents()
    assert not controller.display_window.transcript.history.segments
    assert not controller.overlay._messages


def test_clear_discards_source_and_translation_queued_from_worker(controller):
    controller.start()
    controller.pipeline._msg_id = 7

    def worker():
        controller.overlay.add_message(7, "12:00", "Queued.", "en", 10)
        controller.overlay.update_streaming(7, "Intermediate")
        controller.overlay.update_translation(7, "Finished.", 20)

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()
    controller.clear()
    QApplication.instance().processEvents()
    controller.display_window.transcript.flush()
    assert not controller.display_window.transcript.history.segments
    assert not controller._pending
    assert controller.window.status_label.text() == "Listening"


def test_translation_finishing_before_source_does_not_leave_translating_status(controller):
    controller.start()
    controller.translation_received(1, "Translation.", 20)
    controller.source_received(1, "12:00", "Source.", "en", 10)
    assert not controller._pending
    assert controller.window.status_label.text() == "Listening"
    assert controller.display_window.transcript.history.text("source") == "Source."


def test_stream_eviction_does_not_leave_translating_status_stuck(controller):
    controller.start()
    history = controller.display_window.transcript.history
    history.max_characters = 20
    controller.source_received(1, "12:00", "First.", "en", 10)
    controller.source_received(2, "12:00", "Second.", "en", 10)
    assert controller._pending == {1, 2}

    controller.translation_streamed(2, "x" * 100)
    assert 1 not in history.segments
    assert controller._pending == {2}
    controller.translation_received(2, "Done.", 20)
    assert not controller._pending
    assert controller.window.status_label.text() == "Listening"


def test_bracketed_translation_is_not_misreported_as_an_error(controller):
    controller.start()
    controller.source_received(1, "12:00", "Source.", "en", 10)
    controller.translation_received(1, "[Note] Translation.", 20)
    assert controller.window.status_label.text() == "Listening"
    assert not controller._error

    controller.source_received(2, "12:00", "Another.", "en", 10)
    controller.translation_received(2, "[error: service unavailable]", 0)
    assert controller.window.status_label.text().startswith("Error")


def test_advanced_subtitle_toggle_and_close_are_persisted(controller):
    checked = []
    controller.overlay.set_subtitle_checked = checked.append
    controller.toggle_subtitles()
    assert controller.subwin.isVisible()
    assert controller.saved_for_test[-1]["subtitle_mode"]["enabled"]
    assert checked[-1] is True
    controller.subwin.close()
    assert not controller.subwin.isVisible()
    assert controller.saved_for_test[-1]["subtitle_mode"]["enabled"] is False
    assert checked[-1] is False


def test_advanced_export_routes_existing_upstream_export_and_overlay_start_stop(controller, monkeypatch):
    exports = []
    monkeypatch.setattr(controller.overlay, "export_messages", lambda kind, parent: exports.append((kind, parent)))
    buttons = {button.text(): button for button in controller.panel.findChildren(QPushButton)}
    for label in ("Export original", "Export translation", "Export both"):
        buttons[label].click()
    assert [kind for kind, _ in exports] == ["original", "translation", "both"]
    assert all(parent is controller.panel for _, parent in exports)
    controller.overlay.start_requested.emit()
    assert controller.pipeline._running
    controller.overlay.stop_requested.emit()
    controller._stop_thread.join(2)
    QApplication.instance().processEvents()
    assert not controller.pipeline._running


def test_quit_during_model_load_waits_for_load_without_starting_audio(controller, monkeypatch):
    app = QApplication.instance()
    quits = []
    monkeypatch.setattr(app, "quit", lambda: quits.append(True))
    apply_settings = controller.panel._apply_settings

    def loading_dialog():
        # Simulate Close arriving through the upstream model dialog's nested
        # event loop, just before model loading returns ready.
        controller.quit()
        assert not controller._stopping
        assert not quits
        apply_settings()

    monkeypatch.setattr(controller.panel, "_apply_settings", loading_dialog)
    controller.start()
    controller._stop_thread.join(2)
    app.processEvents()
    assert controller.pipeline.starts == 0
    assert controller.pipeline.stops == 1
    assert not controller.pipeline._running
    assert quits == [True]


def test_quit_flushes_pending_advanced_settings_save(controller, monkeypatch):
    monkeypatch.setattr(QApplication.instance(), "quit", lambda: None)
    index = controller.panel._asr_lang.findData("ja")
    controller.panel._asr_lang.setCurrentIndex(index)
    assert controller.panel._save_timer.isActive()
    controller.quit()
    assert controller.saved_for_test[-1]["asr_language"] == "ja"
    assert not controller.panel._save_timer.isActive()

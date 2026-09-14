"""OneBoard launch and UI adapter around the unmodified upstream pipeline."""

import logging
import signal
import sys
import threading

# main imports torch before Qt, as required by the Windows runtime.
from main import LiveTranslateApp, create_app_icon, load_config, setup_logging
from PyQt6.QtCore import QObject, QRect, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QHBoxLayout, QLabel, QMessageBox, QPushButton,
)

from audio_capture import list_output_devices
from branding import APP_NAME, APP_SHORT_NAME, COMPANY_NAME
from control_panel import ControlPanel, _load_saved_settings, _save_settings
from i18n import LANGUAGES, set_lang
from log_window import LogWindow
from oneboard_display_window import OneBoardDisplayWindow
from oneboard_log_safety import safe_exception_text
from oneboard_presets import apply_direction, direction_for_settings, fresh_settings
from oneboard_readiness import ReadinessDialog, check_readiness
from oneboard_setup import SetupWizard, first_run_required
from oneboard_updates import UpdateDialog
from oneboard_ui import OneBoardWindow
from subtitle_overlay import SubtitleOverlay
from subtitle_window import SubtitleWindow

log = logging.getLogger("LiveTranslate.OneBoard")

WINDOW_STATE_KEY = "oneboard_windows"


def _screen_for_geometry(rect):
    """Return the active screen containing a useful part of a saved window."""
    best = None
    for screen in QApplication.screens():
        visible = screen.availableGeometry().intersected(rect)
        if (
            visible.width() >= min(100, rect.width())
            and visible.height() >= min(80, rect.height())
        ):
            area = visible.width() * visible.height()
            if best is None or area > best[0]:
                best = (area, screen)
    return best[1] if best else None


def _title_area_is_visible(rect):
    for screen in QApplication.screens():
        available = screen.availableGeometry()
        horizontal = available.intersected(rect).width()
        if (
            horizontal >= min(100, rect.width())
            and available.top() <= rect.top() <= available.bottom()
        ):
            return True
    return False


def _restore_geometry(widget, state):
    if not isinstance(state, dict):
        return False
    try:
        values = tuple(int(state[key]) for key in ("x", "y", "width", "height"))
    except (KeyError, TypeError, ValueError, OverflowError):
        return False
    x, y, width, height = values
    if width < widget.minimumWidth() or height < widget.minimumHeight():
        return False
    coordinate_limit = 2_147_483_647
    if (
        not -coordinate_limit <= x <= coordinate_limit
        or not -coordinate_limit <= y <= coordinate_limit
        or width > coordinate_limit
        or height > coordinate_limit
        or x + width - 1 > coordinate_limit
        or y + height - 1 > coordinate_limit
    ):
        return False
    try:
        rect = QRect(x, y, width, height)
    except OverflowError:
        return False
    screen = _screen_for_geometry(rect)
    if screen is None:
        return False
    screens = QApplication.screens()
    visible_area = sum(
        intersection.width() * intersection.height()
        for current in screens
        if (intersection := current.availableGeometry().intersected(rect)).isValid()
    )
    if (
        visible_area >= rect.width() * rect.height() * 0.8
        and _title_area_is_visible(rect)
    ):
        widget.setGeometry(rect)
        return True
    available = screen.availableGeometry()
    width = max(widget.minimumWidth(), min(width, available.width()))
    height = max(widget.minimumHeight(), min(height, available.height()))
    x = max(
        available.left(),
        min(x, max(available.left(), available.right() - width + 1)),
    )
    y = max(
        available.top(),
        min(y, max(available.top(), available.bottom() - height + 1)),
    )
    rect = QRect(x, y, width, height)
    widget.setGeometry(rect)
    return True


def _geometry_state(widget):
    rect = widget.normalGeometry()
    if not rect.isValid():
        rect = widget.geometry()
    return {
        "x": rect.x(),
        "y": rect.y(),
        "width": rect.width(),
        "height": rect.height(),
    }


class ProductPipeline(LiveTranslateApp):
    """Defer ASR loading to Start; settings remain editable while stopped."""

    allow_model_load = False

    def _switch_asr_engine(self, engine_type):
        if self.allow_model_load:
            return super()._switch_asr_engine(engine_type)


class OneBoardController(QObject):
    stopped = pyqtSignal(str)

    def __init__(self, config, settings, *, pipeline_factory=ProductPipeline,
                 save_settings=_save_settings, readiness_check=check_readiness,
                 readiness_dialog_factory=ReadinessDialog,
                 setup_factory=SetupWizard, update_dialog_factory=UpdateDialog):
        super().__init__()
        self.config = config
        self.save_settings = save_settings
        self.pipeline_factory = pipeline_factory
        self.readiness_check = readiness_check
        self.readiness_dialog_factory = readiness_dialog_factory
        self.setup_factory = setup_factory
        self.update_dialog_factory = update_dialog_factory
        self.pipeline = None
        self._stopping = False
        self._starting = False
        self._stop_after_start = False
        self._quitting = False
        self._pending = set()
        self._error = ""
        limits = config.get("oneboard", {})
        self.window = OneBoardWindow()
        self.display_window = OneBoardDisplayWindow(
            max_segments=settings.get(
                "oneboard_history_segments", limits.get("history_segments", 500)
            ),
            max_characters=settings.get(
                "oneboard_history_characters", limits.get("history_characters", 100000)
            ),
        )
        self.panel = ControlPanel(config, saved_settings=settings)
        self.overlay = SubtitleOverlay(config["subtitle"])
        self.subwin = SubtitleWindow(settings.get("subtitle_mode"))
        self.logs = LogWindow()
        self._log_handler = self.logs.get_handler()
        logging.getLogger().addHandler(self._log_handler)
        self._restore_product_windows(settings)
        self._window_save_timer = QTimer(self)
        self._window_save_timer.setSingleShot(True)
        self._window_save_timer.setInterval(300)
        self._window_save_timer.timeout.connect(self._save_window_geometries)
        self.window.start_requested.connect(self.start)
        self.window.stop_requested.connect(self.stop)
        self.window.settings_requested.connect(self.show_advanced)
        self.window.display_requested.connect(self.show_display)
        self.window.direction_changed.connect(self.set_direction)
        self.window.audio_changed.connect(self.set_audio)
        self.window.clear_requested.connect(self.clear)
        self.window.geometry_changed.connect(self._schedule_window_geometry_save)
        self.display_window.geometry_changed.connect(self._schedule_window_geometry_save)
        self.display_window.window_closed.connect(self._display_closed)
        self.panel.settings_changed.connect(self.settings_changed)
        self.panel.model_changed.connect(self.model_changed)
        self.panel.models_list_changed.connect(self.overlay.set_models)
        self.panel.subtitle_settings_changed.connect(self.apply_subtitles)
        self.panel.reset_positions.connect(self.reset_positions)
        # The upstream overlay already exposes ordered, thread-safe signals for
        # committed ASR, partial translation, and final translation. Subscribe
        # here instead of changing recognition/translation worker code.
        self.overlay.add_message_signal.connect(self.source_received)
        self.overlay.update_streaming_signal.connect(self.translation_streamed)
        self.overlay.update_translation_signal.connect(self.translation_received)
        self.overlay.update_asr_device_signal.connect(self.asr_status)
        self.overlay.settings_requested.connect(self.show_advanced)
        self.overlay.start_requested.connect(self.start)
        self.overlay.stop_requested.connect(self.stop)
        self.overlay.hide_requested.connect(self.overlay.hide)
        self.overlay.quit_requested.connect(self.quit)
        self.overlay.source_language_changed.connect(self.set_source)
        self.overlay.target_language_changed.connect(self.set_target)
        self.overlay.model_switch_requested.connect(self.switch_model)
        self.overlay.subtitle_toggled.connect(self.toggle_subtitles)
        # Keep the Advanced overlay and Control Window Clear actions in sync;
        # both displays subscribe to the same live message stream.
        self.overlay._handle.clear_clicked.connect(self.clear)
        self.subwin.window_closed.connect(self.subtitle_closed)
        self.stopped.connect(self.stop_finished)
        self._add_advanced_actions()
        self.settings_changed(self.panel.get_settings())
        self.apply_subtitles(settings.get("subtitle_mode") or {})
        self.refresh_audio()
        self._audio_timer = QTimer(self)
        self._audio_timer.setInterval(5000)
        self._audio_timer.timeout.connect(self.refresh_audio)
        self._audio_timer.start()
        self.window.closeEvent = self.close_event

    def _default_product_geometries(self):
        screen = QApplication.primaryScreen()
        available = screen.availableGeometry()
        margin = 30
        control_width = min(580, max(self.window.minimumWidth(), available.width() - 2 * margin))
        control_height = min(250, max(self.window.minimumHeight(), available.height() - 2 * margin))
        display_width = min(900, max(self.display_window.minimumWidth(), available.width() - 2 * margin))
        display_height = min(680, max(self.display_window.minimumHeight(), available.height() - 2 * margin))
        control_x = available.left() + margin
        control_y = available.top() + margin
        if available.width() >= control_width + display_width + 3 * margin:
            display_x = control_x + control_width + margin
            display_y = control_y
        else:
            display_x = max(available.left() + margin, available.right() - display_width - margin + 1)
            display_y = min(
                available.bottom() - display_height - margin + 1,
                control_y + max(50, control_height // 3),
            )
            display_y = max(available.top() + margin, display_y)
        return (
            QRect(control_x, control_y, control_width, control_height),
            QRect(display_x, display_y, display_width, display_height),
        )

    def _restore_product_windows(self, settings):
        states = settings.get(WINDOW_STATE_KEY) or {}
        defaults = self._default_product_geometries()
        for widget, name, fallback in (
            (self.window, "control", defaults[0]),
            (self.display_window, "display", defaults[1]),
        ):
            if not _restore_geometry(widget, states.get(name)):
                widget.setGeometry(fallback)

    def _capture_window_geometries(self):
        windows = {
            "control": _geometry_state(self.window),
            "display": _geometry_state(self.display_window),
        }
        self.panel._current_settings[WINDOW_STATE_KEY] = windows
        return windows

    def _schedule_window_geometry_save(self):
        if not self._quitting:
            self._window_save_timer.start()

    def _save_window_geometries(self):
        self._window_save_timer.stop()
        self._capture_window_geometries()
        self.save_settings(self.panel.get_settings())

    def _display_closed(self):
        if not self._quitting:
            self._save_window_geometries()

    def show_windows(self):
        """Show both product windows, leaving the compact controls in front."""
        self.display_window.show()
        self.window.show()
        self.window.raise_()

    def show_display(self):
        if self.display_window.isVisible() and not self.display_window.isMinimized():
            self.display_window.raise_()
            self.display_window.activateWindow()
            return
        was_maximized = self.display_window.isMaximized()
        was_minimized = self.display_window.isMinimized()
        state = _geometry_state(self.display_window)
        if not _restore_geometry(self.display_window, state):
            self.display_window.setGeometry(self._default_product_geometries()[1])
        if was_maximized:
            self.display_window.showMaximized()
        elif was_minimized:
            self.display_window.showNormal()
        else:
            self.display_window.show()
        self.display_window.raise_()
        self.display_window.activateWindow()

    def _add_advanced_actions(self):
        row = QHBoxLayout()
        for label, action in (("Logs", self.show_logs),
                              ("System readiness", self.show_readiness),
                              ("Run setup again", self.show_setup),
                              ("Version and updates", self.show_updates),
                              ("Subtitle control overlay", self.show_overlay),
                              ("Subtitle window", self.toggle_subtitles)):
            button = QPushButton(label)
            button.clicked.connect(action)
            row.addWidget(button)
        self.panel.layout().addLayout(row)
        language_row = QHBoxLayout()
        language_row.addWidget(QLabel("Translation language"))
        self.target_combo = QComboBox()
        for code, label in LANGUAGES:
            if code != "auto":
                self.target_combo.addItem(label or code, code)
        self.target_combo.currentIndexChanged.connect(
            lambda _: self.set_target(self.target_combo.currentData()))
        language_row.addWidget(self.target_combo)
        self.panel.layout().addLayout(language_row)
        export_row = QHBoxLayout()
        for label, kind in (("Export original", "original"),
                            ("Export translation", "translation"),
                            ("Export both", "both")):
            button = QPushButton(label)
            button.clicked.connect(
                lambda checked=False, value=kind: self.overlay.export_messages(value, parent=self.panel))
            export_row.addWidget(button)
        self.panel.layout().addLayout(export_row)

    def show_advanced(self):
        self.panel.show()
        self.panel.raise_()
        self.panel.activateWindow()

    def show_logs(self):
        self.logs.show()
        self.logs.raise_()

    def show_readiness(self):
        dialog = self.readiness_dialog_factory(
            self.config, self.panel.get_settings(), parent=self.panel)
        dialog.exec()
        return dialog.report

    def show_setup(self):
        if self._busy():
            QMessageBox.information(
                self.panel, APP_NAME,
                "Stop live translation before running Setup. This prevents the "
                "setup audio test from competing for the active audio device.",
            )
            return
        settings = self.panel.get_settings()
        dialog = self.setup_factory(
            self.config, settings, self.save_settings, parent=self.panel)
        if dialog.exec():
            self.panel._current_settings.update(settings)
            self._sync_audio_controls(settings)
            self.settings_changed(self.panel.get_settings())

    def show_updates(self):
        dialog = self.update_dialog_factory(
            self.panel.get_settings(), parent=self.panel)
        dialog.exec()

    def _sync_audio_controls(self, settings):
        audio = settings.get("audio_device")
        audio_index = (0 if audio == "__disabled__" else 1 if audio is None
                       else self.panel._audio_device.findText(audio))
        if audio_index >= 0:
            self.panel._audio_device.blockSignals(True)
            self.panel._audio_device.setCurrentIndex(audio_index)
            self.panel._audio_device.blockSignals(False)
        microphone = settings.get("mic_device")
        mic_index = (0 if microphone is None else 1 if microphone == "__default__"
                     else self.panel._mic_device.findText(microphone))
        if mic_index >= 0:
            self.panel._mic_device.blockSignals(True)
            self.panel._mic_device.setCurrentIndex(mic_index)
            self.panel._mic_device.blockSignals(False)

    def show_overlay(self):
        self.overlay.show()
        self.overlay.raise_()

    def reset_positions(self):
        control_rect, display_rect = self._default_product_geometries()
        self.window.setGeometry(control_rect)
        self.display_window.setGeometry(display_rect)
        screen = QApplication.primaryScreen().availableGeometry()
        self.subwin.move(screen.left() + 100, screen.top() + 100)
        self.overlay.move(
            screen.right() - self.overlay.width() - 50,
            screen.bottom() - self.overlay.height() - 100,
        )
        settings = self.panel._current_settings
        settings.update({
            "overlay_x": self.overlay.x(),
            "overlay_y": self.overlay.y(),
            "overlay_w": self.overlay.width(),
            "overlay_h": self.overlay.height(),
        })
        subtitle = dict(settings.get("subtitle_mode") or {})
        subtitle.update(window_x=self.subwin.x(), window_y=self.subwin.y())
        self.panel.update_subtitle_settings(subtitle)
        self._save_window_geometries()

    def refresh_audio(self):
        try:
            self.window.set_audio_devices(list_output_devices(),
                                         self.panel.get_settings().get("audio_device"))
        except Exception as exc:
            log.warning("Audio device scan: %s", exc)

    def settings_changed(self, settings):
        self.window.set_direction(direction_for_settings(settings))
        self.window.set_audio_device(settings.get("audio_device"))
        source = settings.get("asr_language", "auto")
        target = settings.get("target_language", "vi")
        self.overlay.set_source_language(source)
        self.overlay.set_target_language(target)
        self.target_combo.blockSignals(True)
        self.target_combo.setCurrentIndex(self.target_combo.findData(target))
        self.target_combo.blockSignals(False)
        self.overlay.set_models(settings.get("models", []), settings.get("active_model", 0))
        style = settings.get("style") or {}
        self.overlay.apply_style(style)
        self.display_window.apply_style(style)
        if self.pipeline:
            self.pipeline._on_settings_changed(settings)
            self.pipeline._on_target_language_changed(target)

    def set_direction(self, key):
        if self._busy():
            return
        settings = apply_direction(self.panel.get_settings(), key)
        self.panel._current_settings.update(settings)
        self._sync_source(settings["asr_language"])
        self.settings_changed(settings)
        self.save_settings(settings)

    def _sync_source(self, code):
        combo = self.panel._asr_lang
        combo.blockSignals(True)
        combo.setCurrentIndex(combo.findData(code))
        combo.blockSignals(False)

    def set_source(self, code):
        self.panel._current_settings.update(asr_language=code, source_language=code)
        self._sync_source(code)
        self.settings_changed(self.panel.get_settings())
        self.save_settings(self.panel.get_settings())

    def set_target(self, code):
        if not code:
            return
        self.panel._current_settings["target_language"] = code
        self.settings_changed(self.panel.get_settings())
        self.save_settings(self.panel.get_settings())

    def set_audio(self, device):
        self.panel._current_settings["audio_device"] = device
        self._sync_audio_controls(self.panel.get_settings())
        self.settings_changed(self.panel.get_settings())
        self.save_settings(self.panel.get_settings())

    def model_changed(self, model):
        if self.pipeline:
            self.pipeline._on_model_changed(model)

    def switch_model(self, index):
        if not 0 <= index < len(self.panel.get_settings().get("models", [])):
            return
        self.panel._current_settings["active_model"] = index
        self.panel._refresh_model_list()
        model = self.panel.get_active_model()
        if model:
            self.model_changed(model)
        self.settings_changed(self.panel.get_settings())
        self.save_settings(self.panel.get_settings())

    def apply_subtitles(self, settings):
        self.subwin.apply_settings(settings)
        self.subwin.setVisible(settings.get("enabled", False))
        self.overlay.set_subtitle_checked(settings.get("enabled", False))

    def toggle_subtitles(self):
        settings = dict(self.panel.get_settings().get("subtitle_mode") or {})
        settings["enabled"] = not self.subwin.isVisible()
        self.panel.update_subtitle_settings(settings)
        self.apply_subtitles(settings)
        self.save_settings(self.panel.get_settings())

    def subtitle_closed(self):
        settings = dict(self.panel.get_settings().get("subtitle_mode") or {})
        settings["enabled"] = False
        self.panel.update_subtitle_settings(settings)
        self.overlay.set_subtitle_checked(False)
        self.save_settings(self.panel.get_settings())

    def _busy(self):
        return self._starting or self._stopping or bool(self.pipeline and self.pipeline._running)

    def start(self):
        if self._busy() or self._quitting:
            return
        self._starting = True
        self._error = ""
        self.window.start_stop_button.setEnabled(False)
        self.window.set_status("Ready", "Checking system readiness…")
        try:
            settings = self.panel.get_settings()
            report = self.readiness_check(self.config, settings)
            if not report.ready:
                dialog = self.readiness_dialog_factory(
                    self.config, settings, parent=self.window)
                accepted = dialog.exec()
                if not accepted or not dialog.report or not dialog.report.ready:
                    detail = (dialog.report.blocking[0].detail
                              if dialog.report and dialog.report.blocking else
                              "Complete the readiness actions before starting.")
                    self._error = detail
                    self.window.set_status("Error", detail)
                    return
            self.window.set_status("Ready", "Preparing speech recognition…")
            if self.pipeline is None:
                self.pipeline = self.pipeline_factory(self.config)
                self.pipeline.set_overlay(self.overlay)
                self.pipeline.set_subtitle_window(self.subwin)
                # The adapter owns settings signals, avoiding eager ASR loads.
                self.pipeline._panel = self.panel
            self.pipeline.allow_model_load = True
            self.panel._apply_settings()
            # Upstream model dialogs run a nested Qt event loop. A Close/Stop
            # request received there must never race worker loading or start
            # capture after the user has already requested shutdown.
            if self._quitting or self._stop_after_start:
                return
            model = self.panel.get_active_model()
            if model:
                self.model_changed(model)
            if not self.pipeline._asr_ready:
                raise RuntimeError("Speech recognition is unavailable. Open Settings to prepare the selected model.")
            self.pipeline.start()
            self._error = ""
            self.window.set_running(True)
            self.overlay.set_running(True)
            self.window.set_status("Listening")
        except Exception as exc:
            log.exception("Unable to start")
            self._error = safe_exception_text(exc)
            self.window.set_status("Error", self._error)
            if self.pipeline and self.pipeline._running:
                self.stop()
        finally:
            self._starting = False
            self.window.start_stop_button.setEnabled(True)
            if self._quitting or self._stop_after_start:
                self._stop_after_start = False
                if self.pipeline:
                    self.stop()
                else:
                    QApplication.instance().quit()

    def stop(self):
        if self._starting:
            self._stop_after_start = True
            return
        if self._stopping or not self.pipeline:
            return
        self._stopping = True
        self.pipeline.allow_model_load = False
        self.window.set_status("Ready", "Stopping…")
        self.window.setEnabled(False)
        self.panel.setEnabled(False)
        # Stop the Qt timer in its owning thread. The existing pipeline cleanup
        # can wait for ASR/translation, so perform that wait outside the UI thread.
        timer = self.pipeline._mem_periodic_timer
        if timer:
            timer.stop()
            self.pipeline._mem_periodic_timer = None

        def finish():
            error = ""
            try:
                self.pipeline.stop()
            except Exception as exc:
                log.exception("Unable to stop")
                error = safe_exception_text(exc)
            self.stopped.emit(error)
        self._stop_thread = threading.Thread(target=finish, daemon=True)
        self._stop_thread.start()

    def stop_finished(self, error):
        self._stopping = False
        self._pending.clear()
        self.window.setEnabled(True)
        self.panel.setEnabled(True)
        self.window.set_running(False)
        self.overlay.set_running(False)
        error = error or self._error
        self.window.set_status("Error" if error else "Ready", error)
        if self._quitting:
            QApplication.instance().quit()

    def source_received(self, msg_id, timestamp, original, source_lang, asr_ms):
        transcript = self.display_window.transcript
        if msg_id <= transcript.history.discarded_through:
            return
        transcript.add_source(msg_id, original, final=True)
        self._pending.intersection_update(transcript.history.segments)
        entry = transcript.history.segments.get(msg_id)
        if entry is not None and not entry.translation_final:
            self._pending.add(msg_id)
        self._refresh_status()

    def translation_streamed(self, msg_id, text):
        transcript = self.display_window.transcript
        transcript.update_translation(msg_id, text)
        # A large stream can evict older segments under the character bound.
        # Do not leave an evicted message marked as translating forever.
        previous = len(self._pending)
        self._pending.intersection_update(transcript.history.segments)
        if len(self._pending) != previous:
            self._refresh_status()

    def translation_received(self, msg_id, text, elapsed):
        text = text or ""
        transcript = self.display_window.transcript
        if msg_id <= transcript.history.discarded_through:
            return
        transcript.update_translation(msg_id, text, final=True)
        self._pending.intersection_update(transcript.history.segments)
        self._pending.discard(msg_id)
        # Upstream marks translation failures with bracketed text and a zero
        # elapsed time. Legitimate translations can also begin with a bracket.
        if text.startswith("[") and elapsed <= 0:
            self._error = "Translation failed. Open Settings or Logs for details."
        self._refresh_status()

    def _refresh_status(self):
        if self._stopping or self._quitting:
            return
        running = bool(self.pipeline and self.pipeline._running)
        status = "Ready"
        if self._error:
            status = "Error"
        elif running:
            status = "Translating" if self._pending else "Listening"
        self.window.set_status(status, self._error)

    def asr_status(self, status):
        if "unavailable" in status.lower():
            self.window.set_status("Error", "Speech recognition is unavailable. Open Settings for details.")

    def clear(self):
        cutoff = self.pipeline._msg_id if self.pipeline else None
        self.display_window.transcript.clear(cutoff)
        self.overlay.clear()
        self._pending.clear()
        self._error = ""
        self._refresh_status()

    def close_event(self, event):
        event.ignore()
        self.quit()

    def quit(self):
        self._quitting = True
        self._window_save_timer.stop()
        self._capture_window_geometries()
        # Capture controls may have an outstanding debounced settings save.
        # Flush it before persistence, but never re-enter an active model load.
        if not self._starting and self.panel._save_timer.isActive():
            self.panel._save_timer.stop()
            if self.pipeline:
                self.pipeline.allow_model_load = False
            self.panel._apply_settings()
        self.save_settings(self.panel.get_settings())
        if self._starting or self._stopping:
            return
        if self.pipeline and (self.pipeline._running or self.pipeline._asr_ready or self._stopping):
            self.stop()
        else:
            QApplication.instance().quit()


def run():
    setup_logging()
    config = load_config()
    import torch
    settings = _load_saved_settings() or fresh_settings(config, gpu_available=torch.cuda.is_available())
    set_lang(settings.get("ui_lang", "en"))
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_SHORT_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName(COMPANY_NAME)
    app.setFont(QFont("Segoe UI", 10))
    app.setWindowIcon(create_app_icon())
    app.setQuitOnLastWindowClosed(False)
    if first_run_required(settings):
        # Cancelling leaves setup incomplete and opens the application. This
        # keeps Advanced available and shows setup again on the next launch.
        SetupWizard(config, settings, _save_settings).exec()
    controller = OneBoardController(config, settings)
    controller.show_windows()
    signal.signal(signal.SIGINT, lambda *_: controller.quit())
    timer = QTimer()
    timer.timeout.connect(lambda: None)
    timer.start(200)
    sys.exit(app.exec())

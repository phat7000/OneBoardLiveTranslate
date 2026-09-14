"""Reopenable first-run setup over the upstream model/audio facilities."""

import threading
import time

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox, QFormLayout, QLabel, QMessageBox, QProgressBar, QPushButton,
    QVBoxLayout, QWizard, QWizardPage,
)

from branding import APP_NAME
from oneboard_readiness import (
    DEFAULT_TRANSLATION_MODEL, ReadinessPanel, selected_asr,
    selected_translation, uses_local_ollama,
)


def first_run_required(settings):
    return not (settings or {}).get("oneboard_setup_completed", False)


def test_audio_source(settings, progress, cancel, *, duration=5.0):
    """Capture briefly for a level test only; audio never reaches ASR or disk."""
    from audio_capture import AudioCapture
    import numpy as np

    capture = AudioCapture(device=settings.get("audio_device"))
    peak = 0.0
    try:
        capture.set_mic_device(settings.get("mic_device"))
        capture.start()
        deadline = time.monotonic() + duration
        while not cancel.is_set() and time.monotonic() < deadline:
            captured = capture.get_audio(timeout=0.25)
            if captured is None:
                continue
            # AudioCapture exposes the mixed samples together with the optional
            # microphone level.  Keep accepting a bare array for lightweight
            # capture adapters, but measure only the sample payload.
            samples = captured[0] if isinstance(captured, tuple) else captured
            if samples is not None and len(samples):
                level = float(np.sqrt(np.mean(np.square(samples.astype(float)))))
                peak = max(peak, level)
                progress(min(100, int(level * 500)))
    finally:
        capture.stop()
    return peak


class _CheckPage(QWizardPage):
    def __init__(self, title, explanation, config, settings, codes=None):
        super().__init__()
        self.setTitle(title)
        layout = QVBoxLayout(self)
        label = QLabel(explanation)
        label.setWordWrap(True)
        layout.addWidget(label)
        self.checks = ReadinessPanel(config, settings, self, codes=codes)
        layout.addWidget(self.checks)

    def initializePage(self):
        self.checks.refresh()

    def cleanupPage(self):
        self.checks._cancel.set()


class _AudioSignals(QObject):
    level = pyqtSignal(int)
    finished = pyqtSignal(str)


class _AudioPage(_CheckPage):
    def __init__(self, config, settings):
        super().__init__("Audio source and test",
                         "Choose the sound to translate. Play speech, then test for five seconds. "
                         "The test measures volume and does not save a recording.",
                         config, settings, codes={"audio"})
        self.settings = settings
        self.cancel_test = threading.Event()
        self.testing = False
        self._signals = _AudioSignals(self)
        form = QFormLayout()
        self.output = QComboBox()
        self.microphone = QComboBox()
        form.addRow("System audio", self.output)
        form.addRow("Microphone", self.microphone)
        self.layout().insertLayout(1, form)
        self.test_button = QPushButton("Test audio for 5 seconds")
        self.test_button.clicked.connect(self._start_test)
        self.layout().addWidget(self.test_button)
        self.meter = QProgressBar()
        self.meter.setRange(0, 100)
        self.meter.setValue(0)
        self.layout().addWidget(self.meter)
        self.test_status = QLabel("A silent device can still be ready; start playback to see a level.")
        self.test_status.setWordWrap(True)
        self.layout().addWidget(self.test_status)
        self._signals.level.connect(self.meter.setValue)
        self._signals.finished.connect(self._test_finished)
        self.output.currentIndexChanged.connect(self._save_selection)
        self.microphone.currentIndexChanged.connect(self._save_selection)

    def initializePage(self):
        from audio_capture import list_input_devices, list_output_devices

        for combo, options, current, default in (
            (self.output, list_output_devices, self.settings.get("audio_device"), None),
            (self.microphone, list_input_devices, self.settings.get("mic_device"), "__default__"),
        ):
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("Disabled", "__disabled__" if combo is self.output else None)
            combo.addItem("System default", default)
            try:
                for name in options():
                    combo.addItem(name, name)
            except Exception:
                pass  # The readiness result below contains actionable device errors.
            index = combo.findData(current)
            if index < 0:
                combo.addItem(f"Unavailable: {current}", current)
                index = combo.count() - 1
            combo.setCurrentIndex(index)
            combo.blockSignals(False)
        super().initializePage()

    def _save_selection(self):
        self.settings["audio_device"] = self.output.currentData()
        self.settings["mic_device"] = self.microphone.currentData()
        self.checks.refresh()

    def _start_test(self):
        if self.testing:
            return
        self.testing = True
        self.cancel_test.clear()
        self.test_button.setEnabled(False)
        self.output.setEnabled(False)
        self.microphone.setEnabled(False)
        self.test_status.setText("Listening for five seconds… play speech now.")
        selected = dict(self.settings)

        def worker():
            try:
                peak = test_audio_source(selected, self._signals.level.emit, self.cancel_test)
                message = ("Audio detected. The selected source is ready." if peak > 0.001 else
                           "No audible sound detected. Start playback or check the selected device and volume.")
                if self.cancel_test.is_set():
                    message = "Audio test stopped."
            except Exception as exc:
                message = f"Audio test failed ({type(exc).__name__}). Check the selected source and try again."
            try:
                self._signals.finished.emit(message)
            except RuntimeError:
                pass

        threading.Thread(target=worker, daemon=True, name="OneBoardAudioTest").start()

    def _test_finished(self, message):
        self.testing = False
        self.test_button.setEnabled(True)
        self.output.setEnabled(True)
        self.microphone.setEnabled(True)
        self.test_status.setText(message)

    def cleanupPage(self):
        self.cancel_test.set()
        super().cleanupPage()

    def validatePage(self):
        self.cancel_test.set()
        return True


class SetupWizard(QWizard):
    """Persist normal settings on Finish, including when preparation is postponed.

    `settings` is the caller's mutable settings dictionary; `save_settings` is
    the normal application's save callback taking one dictionary. Reopening
    respects all Advanced selections and does not reset to MVP defaults.
    """

    def __init__(self, config, settings, save_settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{APP_NAME} — Setup")
        self.resize(680, 720)
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setOption(QWizard.WizardOption.NoBackButtonOnStartPage)
        self.settings = settings
        self.working_settings = dict(settings)
        self._save_settings = save_settings
        self._pages = []

        welcome = QWizardPage()
        welcome.setTitle(f"Welcome to {APP_NAME}")
        layout = QVBoxLayout(welcome)
        intro = QLabel("Translate English and Vietnamese speech with a live original transcript "
                       "and translation. Setup checks your PC, prepares speech recognition and "
                       "Ollama translation, then tests your audio.\n\n"
                       "The recommended speech model is Whisper Small. Models download only "
                       "after you approve. CPU mode is supported.\n\n"
                       "You can postpone preparation, open the application and return to Setup "
                       "from Settings / Advanced. Start checks required components again.")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.addPage(welcome)

        self._add_checks("System check", "Check Windows support, audio, CPU/GPU, speech and translation. "
                         "Performance advice does not prevent use.", config)

        engine, model, _ = selected_asr(config, self.working_settings)
        self._add_checks("Speech recognition model",
                         f"Recommended: faster-whisper Small. Current selection: {engine} / {model}. "
                         "Download missing speech models below. All other engines remain in Advanced.",
                         config, {"asr_runtime", "vad_model", "asr_model"})

        local = uses_local_ollama(config, self.working_settings)
        self._add_checks("Translation engine",
                         "Ollama runs translation locally. If needed, open its official installer page. "
                         "Windows may ask for installation approval. Return here and check again." if local else
                         "Your Advanced translation service is selected. You can keep using it; "
                         "local Ollama is optional. Configure its connection in Advanced.",
                         config, {"ollama_install", "ollama_service", "translation_service"})
        translation = selected_translation(config, self.working_settings)
        self._add_checks("Translation model",
                         f"Current model: {translation.get('model', DEFAULT_TRANSLATION_MODEL)}. "
                         "Approve any download explicitly. Downloads may use several GB; progress "
                         "and cancellation appear here." if local else
                         "The selected Advanced service manages its own translation models.",
                         config, {"translation_model", "translation_service"})

        self.audio_page = _AudioPage(config, self.working_settings)
        self._pages.append(self.audio_page)
        self.addPage(self.audio_page)
        self.complete_page = self._add_checks("Setup review",
                                              "Finish saves your choices and opens the application. "
                                              "Any missing components remain listed below and can be "
                                              "prepared later from Settings / Advanced. "
                                              "A successful audio test confirms capture, while Start "
                                              "loads the selected speech engine and begins translation.", config)
        self.setButtonText(QWizard.WizardButton.FinishButton, "Finish and open application")

    def _add_checks(self, title, description, config, codes=None):
        page = _CheckPage(title, description, config, self.working_settings, codes)
        self._pages.append(page)
        self.addPage(page)
        return page

    def accept(self):
        candidate = dict(self.settings)
        for key in ("audio_device", "mic_device"):
            if key in self.working_settings:
                candidate[key] = self.working_settings[key]
        candidate["oneboard_setup_completed"] = True
        try:
            if self._save_settings(candidate) is False:
                raise OSError("settings writer reported a persistence failure")
        except Exception as exc:
            QMessageBox.critical(self, "Settings could not be saved",
                                 f"Setup remains open. Please check that your settings folder is writable "
                                 f"and try again ({type(exc).__name__}).")
            return
        self.settings.update(candidate)
        self._cancel_tasks()
        super().accept()

    def _cancel_tasks(self):
        self.audio_page.cancel_test.set()
        for page in self._pages:
            page.checks._cancel.set()

    def reject(self):
        self._cancel_tasks()
        super().reject()

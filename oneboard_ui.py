"""Compact OneBoard controls; the upstream Control Panel stays Advanced."""

from PyQt6.QtCore import pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QPushButton, QToolButton, QVBoxLayout, QWidget,
)

from branding import APP_NAME
from oneboard_presets import DIRECTIONS
class OneBoardWindow(QWidget):
    """The primary Control Window for the OneBoard product experience."""

    start_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    display_requested = pyqtSignal()
    direction_changed = pyqtSignal(str)
    audio_changed = pyqtSignal(object)
    clear_requested = pyqtSignal()
    geometry_changed = pyqtSignal()
    _status_received = pyqtSignal(str, str)
    _running_received = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{APP_NAME} - Control")
        self.resize(580, 250)
        self.setMinimumSize(480, 220)
        self._running = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)
        title_row = QHBoxLayout()
        title = QLabel(APP_NAME)
        font = title.font()
        font.setPointSize(font.pointSize() + 4)
        font.setBold(True)
        title.setFont(font)
        title_row.addWidget(title)
        title_row.addStretch()
        self.settings_button = QToolButton()
        self.settings_button.setText("⚙")
        self.settings_button.setAccessibleName("Settings and Advanced Control Panel")
        self.settings_button.setToolTip("Settings / Advanced Control Panel")
        self.settings_button.clicked.connect(self.settings_requested)
        title_row.addWidget(self.settings_button)
        layout.addLayout(title_row)

        direction_row = QHBoxLayout()
        direction_row.addWidget(QLabel("Language direction"))
        self.direction_combo = QComboBox()
        for key, (label, _, _) in DIRECTIONS.items():
            self.direction_combo.addItem(label, key)
        self.direction_combo.addItem("Custom (Advanced)", "custom")
        self.direction_combo.setAccessibleName("Language direction")
        self.direction_combo.currentIndexChanged.connect(self._direction_selected)
        direction_row.addWidget(self.direction_combo, 1)
        self.swap_button = QPushButton("⇄ Swap")
        self.swap_button.setToolTip("Swap English and Vietnamese")
        self.swap_button.clicked.connect(self.swap_direction)
        direction_row.addWidget(self.swap_button)
        layout.addLayout(direction_row)

        audio_row = QHBoxLayout()
        audio_row.addWidget(QLabel("Audio source"))
        self.audio_combo = QComboBox()
        self.audio_combo.setAccessibleName("Audio source")
        self.audio_combo.addItem("System Audio (default output)", None)
        self.audio_combo.currentIndexChanged.connect(
            lambda _index: self.audio_changed.emit(self.audio_combo.currentData())
        )
        audio_row.addWidget(self.audio_combo, 1)
        self.start_stop_button = QPushButton("Start")
        self.start_stop_button.setMinimumWidth(90)
        self.start_stop_button.clicked.connect(self._toggle_requested)
        audio_row.addWidget(self.start_stop_button)
        layout.addLayout(audio_row)

        self.status_label = QLabel("Ready")
        self.status_label.setWordWrap(True)
        self.status_label.setAccessibleName("Application status")
        layout.addWidget(self.status_label)
        layout.addStretch(1)
        footer = QHBoxLayout()
        self.display_button = QPushButton("Display Window")
        self.display_button.setAccessibleName("Show transcript Display Window")
        self.display_button.setToolTip("Show the transcript Display Window")
        self.display_button.clicked.connect(self.display_requested)
        footer.addWidget(self.display_button)
        footer.addStretch(1)
        self.clear_button = QPushButton("Clear Transcript")
        self.clear_button.clicked.connect(self.clear_requested)
        footer.addWidget(self.clear_button)
        layout.addLayout(footer)
        self._status_received.connect(self._apply_status)
        self._running_received.connect(self._apply_running)

    def _toggle_requested(self):
        (self.stop_requested if self._running else self.start_requested).emit()

    def _direction_selected(self, _index):
        key = self.direction_combo.currentData()
        self.swap_button.setEnabled(key in DIRECTIONS and not self._running)
        if key == "custom":
            self.settings_requested.emit()
        else:
            self.direction_changed.emit(key)

    def swap_direction(self):
        key = self.direction_combo.currentData()
        if key in DIRECTIONS and not self._running:
            self.direction_combo.setCurrentIndex(1 if key == "en-vi" else 0)

    def set_direction(self, direction):
        index = self.direction_combo.findData(direction)
        self.direction_combo.blockSignals(True)
        self.direction_combo.setCurrentIndex(index if index >= 0 else 2)
        self.direction_combo.blockSignals(False)
        self.swap_button.setEnabled(direction in DIRECTIONS and not self._running)

    def set_audio_devices(self, names, selected=None):
        self.audio_combo.blockSignals(True)
        self.audio_combo.clear()
        self.audio_combo.addItem("System Audio (default output)", None)
        for name in dict.fromkeys(names):
            self.audio_combo.addItem(name, name)
        self.audio_combo.blockSignals(False)
        self.set_audio_device(selected)

    def set_audio_device(self, selected):
        self.audio_combo.blockSignals(True)
        index = self.audio_combo.findData(selected)
        if index < 0:
            label = "System Audio disabled (Advanced)" if selected == "__disabled__" else str(selected)
            self.audio_combo.addItem(label, selected)
            index = self.audio_combo.count() - 1
        self.audio_combo.setCurrentIndex(index)
        self.audio_combo.blockSignals(False)

    def set_running(self, running):
        self._running_received.emit(bool(running))

    @pyqtSlot(bool)
    def _apply_running(self, running):
        self._running = running
        self.start_stop_button.setText("Stop" if running else "Start")
        self.direction_combo.setEnabled(not running)
        self.swap_button.setEnabled(not running and self.direction_combo.currentData() in DIRECTIONS)
        self.audio_combo.setEnabled(not running)

    def set_status(self, status, detail=""):
        self._status_received.emit(str(status), str(detail))

    @pyqtSlot(str, str)
    def _apply_status(self, status, detail):
        self.status_label.setText(f"{status} · {detail}" if detail else status)

    def moveEvent(self, event):
        super().moveEvent(event)
        self.geometry_changed.emit()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.geometry_changed.emit()

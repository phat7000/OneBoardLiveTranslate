"""Dedicated OneBoard reading window backed by the shared transcript history."""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from branding import APP_NAME
from oneboard_transcript_view import OneBoardTranscriptView
from subtitle_overlay import DEFAULT_STYLE


class OneBoardDisplayWindow(QWidget):
    """Independent presentation window containing only accumulated transcript text."""

    window_closed = pyqtSignal()
    geometry_changed = pyqtSignal()

    def __init__(self, parent=None, max_segments=500, max_characters=100_000):
        super().__init__(parent)
        self.setWindowTitle(f"{APP_NAME} - Display")
        self.resize(900, 680)
        self.setMinimumSize(540, 420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.transcript = OneBoardTranscriptView(
            self,
            max_segments=max_segments,
            max_characters=max_characters,
        )
        layout.addWidget(self.transcript)
        self._style = dict(DEFAULT_STYLE)
        self.apply_style({})

    def apply_style(self, style):
        """Apply the existing Advanced Style payload to this reading window."""
        style = dict(style or {})
        merged = {**DEFAULT_STYLE, **style}
        if "font_family" in merged and "original_font_family" not in style:
            merged["original_font_family"] = merged["font_family"]
            merged["translation_font_family"] = merged["font_family"]
        self._style = merged
        self.transcript.apply_style(merged)
        opacity = max(30, min(100, int(merged["window_opacity"])))
        self.setWindowOpacity(opacity / 100.0)

    def closeEvent(self, event):
        # QWidget instances are reusable after close. Accepting the event hides
        # this window without affecting the independently owned Control Window.
        self.geometry_changed.emit()
        event.accept()
        self.window_closed.emit()

    def moveEvent(self, event):
        super().moveEvent(event)
        self.geometry_changed.emit()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.geometry_changed.emit()

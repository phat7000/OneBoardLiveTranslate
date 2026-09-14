"""Bounded, ordered continuous transcripts and a thread-safe Qt display."""

from dataclasses import dataclass

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor, QFont, QTextCursor
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QSplitter, QVBoxLayout, QWidget,
)


@dataclass
class TranscriptSegment:
    source: str = ""
    translation: str = ""
    source_final: bool = False
    translation_final: bool = False


def _join_segments(parts):
    # ASR/translation punctuation belongs to each segment. Never invent sentence
    # punctuation, but avoid spaces before punctuation-only incremental fragments.
    result = ""
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if result and part[0] not in ".,!?;:。！？、，；：)]}”’":
            result += " "
        result += part
    return result


class TranscriptHistory:
    """One mutable entry per monotonic upstream message ID, independent of Qt.

    The eviction watermark also rejects late asynchronous results, without keeping
    an unbounded tombstone set. IDs must not restart when capture restarts.
    """

    def __init__(self, max_segments=500, max_characters=100_000):
        if max_segments < 1 or max_characters < 2:
            raise ValueError("Transcript limits must allow one segment and two characters")
        self.max_segments = int(max_segments)
        self.max_characters = int(max_characters)
        self.segments: dict[int, TranscriptSegment] = {}
        self.discarded_through = -1
        self.latest_id = -1

    def _entry(self, msg_id):
        if not isinstance(msg_id, int):
            raise TypeError("Transcript message IDs must be integers")
        self.latest_id = max(self.latest_id, msg_id)
        if msg_id <= self.discarded_through:
            return None
        return self.segments.setdefault(msg_id, TranscriptSegment())

    def add_source(self, msg_id, text, final=False):
        entry = self._entry(msg_id)
        if entry is None or entry.source_final:
            return False
        entry.source = str(text).strip()
        entry.source_final = bool(final)
        self._trim()
        return True

    def update_translation(self, msg_id, text, final=False):
        entry = self._entry(msg_id)
        if entry is None or entry.translation_final:
            return False
        entry.translation = str(text).strip()
        entry.translation_final = bool(final)
        self._trim()
        return True

    @property
    def character_count(self):
        return sum(len(entry.source) + len(entry.translation) for entry in self.segments.values())

    def _trim(self):
        while len(self.segments) > self.max_segments or (
            len(self.segments) > 1 and self.character_count > self.max_characters
        ):
            oldest = min(self.segments)
            del self.segments[oldest]
            self.discarded_through = max(self.discarded_through, oldest)
        if self.character_count > self.max_characters:
            # A single unexpectedly large response must also respect the bound.
            # Keep the latest text in both panes, sharing capacity when necessary.
            entry = next(iter(self.segments.values()))
            source_budget = min(len(entry.source), self.max_characters // 2)
            translation_budget = min(len(entry.translation), self.max_characters - source_budget)
            source_budget = min(len(entry.source), self.max_characters - translation_budget)
            entry.source = entry.source[-source_budget:] if source_budget else ""
            entry.translation = entry.translation[-translation_budget:] if translation_budget else ""

    def clear(self, up_to_id=None):
        cutoff = self.latest_id if up_to_id is None else max(self.latest_id, int(up_to_id))
        self.discarded_through = max(self.discarded_through, cutoff)
        self.latest_id = max(self.latest_id, cutoff)
        self.segments.clear()

    def text(self, field):
        if field not in ("source", "translation"):
            raise ValueError(f"Unknown transcript field: {field}")
        return _join_segments(getattr(self.segments[key], field) for key in sorted(self.segments))


def _rgba(color, opacity):
    parsed = QColor(str(color))
    if not parsed.isValid():
        parsed = QColor("#000000")
    alpha = max(0, min(255, int(opacity)))
    return f"rgba({parsed.red()}, {parsed.green()}, {parsed.blue()}, {alpha})"


class _TranscriptPane(QWidget):
    def __init__(self, title, role, parent=None):
        super().__init__(parent)
        self.setObjectName(f"oneboard{role.title()}Pane")
        self._following = True
        self._rendering = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.heading_widget = QWidget(self)
        self.heading_widget.setObjectName(f"oneboard{role.title()}Header")
        heading = QHBoxLayout(self.heading_widget)
        heading.setContentsMargins(10, 6, 10, 6)
        self.heading_label = QLabel(title, self.heading_widget)
        self.heading_label.setObjectName(f"oneboard{role.title()}Heading")
        heading.addWidget(self.heading_label)
        heading.addStretch()
        self.follow_button = QPushButton("Follow live")
        self.follow_button.setObjectName(f"oneboard{role.title()}Follow")
        self.follow_button.setToolTip("Return to the latest transcript text")
        self.follow_button.hide()
        self.follow_button.clicked.connect(self.follow_live)
        heading.addWidget(self.follow_button)
        layout.addWidget(self.heading_widget)
        self.editor = QPlainTextEdit()
        self.editor.setObjectName(f"oneboard{role.title()}Transcript")
        self.editor.setReadOnly(True)
        self.editor.setUndoRedoEnabled(False)
        self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.editor.setAccessibleName(title)
        self.editor.setPlaceholderText("Transcript will appear here when you start.")
        self.editor.verticalScrollBar().valueChanged.connect(self._scroll_changed)
        layout.addWidget(self.editor)

    def _scroll_changed(self, value):
        if self._rendering:
            return
        scrollbar = self.editor.verticalScrollBar()
        self._following = value >= scrollbar.maximum() - 2
        self.follow_button.setVisible(not self._following)

    def follow_live(self):
        self._following = True
        scrollbar = self.editor.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        self.follow_button.hide()

    def render(self, text):
        old = self.editor.toPlainText()
        if old == text:
            return
        scrollbar = self.editor.verticalScrollBar()
        old_value = scrollbar.value()
        selection = self.editor.textCursor()
        self._rendering = True
        # Streaming usually modifies just the end. Replace only the changed suffix
        # so earlier text and the user's selection remain stable while reading.
        prefix = 0
        for left, right in zip(old, text):
            if left != right:
                break
            prefix += 1
        # QTextCursor positions count UTF-16 units, not Python Unicode code points.
        position = len(old[:prefix].encode("utf-16-le")) // 2
        cursor = QTextCursor(self.editor.document())
        cursor.setPosition(position)
        cursor.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(text[prefix:])
        self.editor.setTextCursor(selection)
        scrollbar.setValue(scrollbar.maximum() if self._following else min(old_value, scrollbar.maximum()))
        self._rendering = False

    def clear(self):
        self._following = True
        self.editor.clear()
        self.follow_button.hide()


class OneBoardTranscriptView(QWidget):
    """Public update methods may be called by ASR/translation worker threads."""

    _source_received = pyqtSignal(int, str, bool)
    _translation_received = pyqtSignal(int, str, bool)
    _clear_received = pyqtSignal(object)

    def __init__(self, parent=None, max_segments=500, max_characters=100_000):
        super().__init__(parent)
        self.setObjectName("oneboardTranscriptView")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.history = TranscriptHistory(max_segments, max_characters)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.source_pane = _TranscriptPane("Original / Source transcript", "source")
        self.translation_pane = _TranscriptPane("Translation", "translation")
        self.source_edit = self.source_pane.editor
        self.translation_edit = self.translation_pane.editor
        self.splitter.addWidget(self.source_pane)
        self.splitter.addWidget(self.translation_pane)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setHandleWidth(8)
        layout.addWidget(self.splitter)
        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.setInterval(40)
        self._render_timer.timeout.connect(self.flush)
        self._source_received.connect(self._receive_source)
        self._translation_received.connect(self._receive_translation)
        self._clear_received.connect(self._receive_clear)

    def apply_style(self, style):
        """Style both panes from the canonical Advanced Style payload."""
        bg = _rgba(style["bg_color"], style["bg_opacity"])
        header = _rgba(style["header_color"], style["header_opacity"])
        radius = max(0, int(style["border_radius"]))
        header_radius = min(radius, 12)
        self.setStyleSheet(
            "QWidget#oneboardTranscriptView {"
            f" background-color: {bg}; border-radius: {radius}px;"
            "}"
            "QSplitter::handle { background-color: transparent; }"
        )
        for pane, family, size, color in (
            (
                self.source_pane,
                style["original_font_family"],
                style["original_font_size"],
                style["original_color"],
            ),
            (
                self.translation_pane,
                style["translation_font_family"],
                style["translation_font_size"],
                style["translation_color"],
            ),
        ):
            pane.heading_widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            pane.heading_widget.setStyleSheet(
                f"QWidget#{pane.heading_widget.objectName()} {{"
                f" background-color: {header}; border-radius: {header_radius}px;"
                "}"
            )
            heading_font = QFont(str(family), max(8, int(size) - 2))
            heading_font.setBold(True)
            pane.heading_label.setFont(heading_font)
            pane.heading_label.setStyleSheet(f"color: {style['timestamp_color']};")
            pane.follow_button.setStyleSheet(
                f"color: {style['timestamp_color']}; background: transparent;"
                f" border: 1px solid {style['timestamp_color']};"
                f" border-radius: {max(2, header_radius // 2)}px; padding: 2px 6px;"
            )
            pane.editor.setFont(QFont(str(family), int(size)))
            pane.editor.setStyleSheet(
                f"color: {color}; background-color: transparent; border: none;"
                " padding: 8px;"
            )

    def add_source(self, msg_id, text, final=False):
        self._source_received.emit(msg_id, text, final)

    def update_translation(self, msg_id, text, final=False):
        self._translation_received.emit(msg_id, text, final)

    def clear(self, up_to_id=None):
        self._clear_received.emit(up_to_id)

    @pyqtSlot(int, str, bool)
    def _receive_source(self, msg_id, text, final):
        if self.history.add_source(msg_id, text, final):
            self._schedule_render()

    @pyqtSlot(int, str, bool)
    def _receive_translation(self, msg_id, text, final):
        if self.history.update_translation(msg_id, text, final):
            self._schedule_render()

    @pyqtSlot(object)
    def _receive_clear(self, up_to_id):
        self._render_timer.stop()
        self.history.clear(up_to_id)
        self.source_pane.clear()
        self.translation_pane.clear()

    def _schedule_render(self):
        if not self._render_timer.isActive():
            self._render_timer.start()

    @pyqtSlot()
    def flush(self):
        """Render pending changes. Only invoke this directly on the GUI thread."""
        self._render_timer.stop()
        self.source_pane.render(self.history.text("source"))
        self.translation_pane.render(self.history.text("translation"))

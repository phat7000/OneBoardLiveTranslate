import os
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# The application imports torch before Qt to avoid Windows DLL conflicts.
import torch  # noqa: F401, E402
import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QComboBox

from oneboard_display_window import OneBoardDisplayWindow
from oneboard_presets import (
    DEFAULT_TRANSLATION_MODEL, apply_direction, direction_for_settings, fresh_settings,
)
from oneboard_transcript_view import OneBoardTranscriptView, TranscriptHistory
from oneboard_ui import OneBoardWindow


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.mark.parametrize("key,source,target", [("en-vi", "en", "vi"), ("vi-en", "vi", "en")])
def test_direction_presets_preserve_advanced_configuration(key, source, target):
    original = {"asr_language": "auto", "models": [{"api_key": "existing"}], "vad_mode": "energy"}
    result = apply_direction(original, key)
    assert result["asr_language"] == result["source_language"] == source
    assert result["target_language"] == target
    assert direction_for_settings(result) == key
    assert result["vad_mode"] == "energy"
    result["models"][0]["api_key"] = "changed"
    assert original["models"][0]["api_key"] == "existing"
    assert original["asr_language"] == "auto"


def test_advanced_languages_are_reported_as_custom():
    assert direction_for_settings({"asr_language": "auto", "target_language": "vi"}) == "custom"
    assert direction_for_settings({"asr_language": "ja", "source_language": "ja", "target_language": "vi"}) == "custom"
    with pytest.raises(ValueError):
        apply_direction({}, "ja-vi")


def test_fresh_defaults_do_not_copy_upstream_translation_credentials():
    from translator import DEFAULT_PROMPT

    defaults = fresh_settings({"translation": {"api_key": "legacy-secret", "model": "legacy"}})
    assert defaults["asr_engine"] == "whisper"
    assert defaults["whisper_model_size"] == "small"
    assert defaults["asr_device"] == "cpu"
    assert defaults["models"][0]["model"] == DEFAULT_TRANSLATION_MODEL
    assert defaults["models"][0]["api_key"] == "ollama"
    assert defaults["system_prompt"] == DEFAULT_PROMPT
    assert defaults["timeout"] == 60
    assert direction_for_settings(defaults) == "en-vi"
    assert fresh_settings({}, gpu_available=True)["asr_device"] == "cuda"


def test_interim_source_replaces_current_segment_and_keeps_punctuation():
    history = TranscriptHistory()
    history.add_source(1, "Today we")
    history.add_source(1, "Today we discuss the plan.", final=True)
    history.add_source(1, "stale interim")
    history.add_source(2, "  First, configure the network.  ", final=True)
    assert history.text("source") == "Today we discuss the plan. First, configure the network."
    assert len(history.segments) == 2


def test_streaming_replaces_only_current_segment_and_orders_out_of_order_results():
    history = TranscriptHistory()
    history.add_source(1, "Hello.", final=True)
    history.add_source(2, "Goodbye.", final=True)
    history.update_translation(2, "Tạm biệt.", final=True)
    history.update_translation(1, "Xin")
    history.update_translation(1, "Xin chào")
    history.update_translation(1, "Xin chào.", final=True)
    history.update_translation(1, "late partial")
    assert history.text("translation") == "Xin chào. Tạm biệt."
    assert len(history.segments) == 2


def test_clear_rejects_late_queued_results_including_not_yet_seen_ids():
    history = TranscriptHistory()
    history.add_source(1, "Before clear")
    history.clear(up_to_id=3)
    assert not history.update_translation(2, "Queued result", final=True)
    assert not history.add_source(3, "Queued source")
    history.add_source(4, "After clear", final=True)
    assert history.text("source") == "After clear"
    assert history.text("translation") == ""


def test_segment_limit_ignores_late_results_for_evicted_segments():
    history = TranscriptHistory(max_segments=2)
    for msg_id in range(5):
        history.add_source(msg_id, f"Message {msg_id}.")
    assert list(history.segments) == [3, 4]
    assert not history.update_translation(1, "Late result", final=True)
    assert history.text("source") == "Message 3. Message 4."


def test_character_limit_is_enforced_even_for_one_oversized_stream():
    history = TranscriptHistory(max_segments=20, max_characters=40)
    history.add_source(1, "old source text")
    history.add_source(2, "s" * 100)
    history.update_translation(2, "t" * 100)
    assert list(history.segments) == [2]
    assert history.character_count <= 40
    assert history.text("source")
    assert history.text("translation")
    history.update_translation(2, "t" * 1_000, final=True)
    assert history.character_count <= 40


def test_primary_controls_emit_actions_and_reflect_running_state(qapp):
    window = OneBoardWindow()
    events = []
    window.start_requested.connect(lambda: events.append("start"))
    window.stop_requested.connect(lambda: events.append("stop"))
    window.settings_requested.connect(lambda: events.append("advanced"))
    window.display_requested.connect(lambda: events.append("display"))
    window.clear_requested.connect(lambda: events.append("clear"))
    window.direction_changed.connect(events.append)
    window.start_stop_button.click()
    window.set_running(True)
    assert not window.direction_combo.isEnabled()
    window.start_stop_button.click()
    window.set_running(False)
    window.swap_button.click()
    window.settings_button.click()
    window.display_button.click()
    window.clear_button.click()
    assert events == ["start", "stop", "vi-en", "advanced", "display", "clear"]
    assert window.direction_combo.currentData() == "vi-en"
    window.set_direction("custom")
    assert not window.swap_button.isEnabled()
    assert events[-1] == "clear"  # synchronization must not emit user actions
    window.close()


def test_control_and_display_windows_have_separate_responsibilities(qapp):
    control = OneBoardWindow()
    display = OneBoardDisplayWindow()
    assert not control.findChildren(OneBoardTranscriptView)
    assert display.findChild(OneBoardTranscriptView) is display.transcript
    assert not display.findChildren(QComboBox)
    assert control.parent() is None
    assert display.parent() is None
    assert control.minimumSize() != display.minimumSize()
    assert display.transcript.splitter.orientation() == Qt.Orientation.Vertical
    assert display.transcript.splitter.widget(0) is display.transcript.source_pane
    assert display.transcript.splitter.widget(1) is display.transcript.translation_pane
    control.close()
    display.close()


def test_display_style_maps_the_existing_advanced_style_payload(qapp):
    display = OneBoardDisplayWindow()
    style = {
        "bg_color": "#123456",
        "bg_opacity": 111,
        "header_color": "#654321",
        "header_opacity": 122,
        "border_radius": 17,
        "original_font_family": "Segoe UI",
        "original_font_size": 13,
        "original_color": "#abcdef",
        "translation_font_family": "Arial",
        "translation_font_size": 19,
        "translation_color": "#fedcba",
        "timestamp_color": "#778899",
        "window_opacity": 73,
    }
    display.apply_style(style)
    transcript = display.transcript
    assert transcript.source_edit.font().pointSize() == 13
    assert transcript.translation_edit.font().pointSize() == 19
    assert "rgba(18, 52, 86, 111)" in transcript.styleSheet()
    assert "border-radius: 17px" in transcript.styleSheet()
    assert "rgba(101, 67, 33, 122)" in transcript.source_pane.heading_widget.styleSheet()
    assert "#abcdef" in transcript.source_edit.styleSheet()
    assert "#fedcba" in transcript.translation_edit.styleSheet()
    assert "#778899" in transcript.source_pane.heading_label.styleSheet()
    assert display.windowOpacity() == pytest.approx(0.73, abs=1 / 255)
    display.close()


def test_display_style_migrates_the_legacy_shared_font_setting(qapp):
    display = OneBoardDisplayWindow()
    display.apply_style({"font_family": "Arial"})
    assert display._style["original_font_family"] == "Arial"
    assert display._style["translation_font_family"] == "Arial"
    display.close()


def test_audio_selection_preserves_advanced_disabled_and_unavailable_device(qapp):
    window = OneBoardWindow()
    events = []
    window.audio_changed.connect(events.append)
    window.set_audio_devices(["Speakers", "Headphones", "Speakers"], "Headphones")
    assert window.audio_combo.count() == 3
    assert window.audio_combo.currentData() == "Headphones"
    assert not events
    window.audio_combo.setCurrentIndex(0)
    assert events == [None]
    window.set_audio_device("__disabled__")
    assert window.audio_combo.currentData() == "__disabled__"
    window.set_audio_devices(["Speakers"], "Missing device")
    assert window.audio_combo.currentData() == "Missing device"
    window.close()


def test_worker_threads_deliver_updates_to_gui_without_duplicate_stream_tokens(qapp):
    view = OneBoardTranscriptView()

    def worker():
        view.add_source(1, "Hello 👋.", final=True)
        view.update_translation(1, "Xin")
        view.update_translation(1, "Xin chào 👋.", final=True)

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()
    assert not view.history.segments  # delivery is queued across threads
    qapp.processEvents()
    view.flush()
    assert view.source_edit.toPlainText() == "Hello 👋."
    assert view.translation_edit.toPlainText() == "Xin chào 👋."
    view.add_source(2, "Next.", final=True)
    view.flush()
    assert view.source_edit.toPlainText() == "Hello 👋. Next."
    view.clear(2)
    view.update_translation(1, "Stale stream")
    view.flush()
    assert view.source_edit.toPlainText() == view.translation_edit.toPlainText() == ""
    view.close()


def test_long_transcript_wraps_and_preserves_manual_scroll_until_follow(qapp):
    view = OneBoardTranscriptView()
    view.resize(560, 380)
    view.show()
    for msg_id in range(50):
        view.add_source(msg_id, f"Sentence {msg_id} is long enough to occupy a substantial amount of horizontal space.", final=True)
    view.flush()
    qapp.processEvents()
    scrollbar = view.source_edit.verticalScrollBar()
    assert scrollbar.maximum() > 0
    assert scrollbar.value() == scrollbar.maximum()
    scrollbar.setValue(0)
    view.add_source(51, "New content arrives while reading history.", final=True)
    view.flush()
    assert scrollbar.value() == 0
    assert view.source_pane.follow_button.isVisible()
    view.source_pane.follow_button.click()
    assert scrollbar.value() == scrollbar.maximum()
    view.close()

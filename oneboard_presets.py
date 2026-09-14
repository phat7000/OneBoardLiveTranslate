"""OneBoard defaults and explicit language presets over upstream settings."""

from copy import deepcopy


OLLAMA_API_BASE = "http://127.0.0.1:11434/v1"
DEFAULT_TRANSLATION_MODEL = "qwen3:4b-instruct-2507-q4_K_M"
DIRECTIONS = {
    "en-vi": ("English → Vietnamese", "en", "vi"),
    "vi-en": ("Vietnamese → English", "vi", "en"),
}


def apply_direction(settings: dict, direction: str) -> dict:
    """Return a copy with explicit ASR/source/target hints; keep advanced options."""
    if direction not in DIRECTIONS:
        raise ValueError(f"Unknown OneBoard language direction: {direction}")
    _, source, target = DIRECTIONS[direction]
    result = deepcopy(settings)
    result.update(asr_language=source, source_language=source, target_language=target)
    return result


def direction_for_settings(settings: dict) -> str:
    for key, (_, source, target) in DIRECTIONS.items():
        if (
            settings.get("asr_language") == source
            and settings.get("source_language") == source
            and settings.get("target_language") == target
        ):
            return key
    return "custom"


def fresh_settings(config: dict, gpu_available: bool = False) -> dict:
    """Build first-use defaults only. Never merge these over saved user settings."""
    from translator import DEFAULT_PROMPT

    asr = config.get("asr", {})
    result = {
        "ui_lang": "en",
        "asr_engine": "whisper",
        "whisper_model_size": "small",
        "asr_device": "cuda" if gpu_available else "cpu",
        "vad_mode": "silero",
        "vad_threshold": asr.get("vad_threshold", 0.5),
        "energy_threshold": 0.02,
        "min_speech_duration": asr.get("min_speech_duration", 1.0),
        "max_speech_duration": asr.get("max_speech_duration", 8.0),
        "silence_mode": "auto",
        "silence_duration": 0.8,
        "sensevoice_pad_seconds": asr.get("sensevoice_pad_seconds", 0.5),
        "whisper_pad_seconds": asr.get("whisper_pad_seconds", 0.5),
        "audio_device": None,
        "mic_device": None,
        "hub": "hf",
        "models": [{
            "name": "Ollama · Qwen 3 4B",
            "api_base": OLLAMA_API_BASE,
            "api_key": "ollama",
            "model": DEFAULT_TRANSLATION_MODEL,
        }],
        "active_model": 0,
        "system_prompt": DEFAULT_PROMPT,
        "timeout": 60,
        "oneboard_history_segments": 500,
        "oneboard_history_characters": 100_000,
        "oneboard_setup_completed": False,
    }
    return apply_direction(result, "en-vi")

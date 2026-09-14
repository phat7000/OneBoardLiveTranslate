from pathlib import Path

import yaml

from oneboard_presets import DEFAULT_TRANSLATION_MODEL


def test_checked_in_fallbacks_match_safe_oneboard_mvp_defaults():
    config = yaml.safe_load(Path("config.yaml").read_text(encoding="utf-8"))

    assert {
        "asr_engine": "whisper",
        "model_size": "small",
        "device": "cpu",
        "compute_type": "int8",
        "language": "en",
    }.items() <= config["asr"].items()
    assert {
        "api_base": "http://127.0.0.1:11434/v1",
        "api_key": "ollama",
        "model": DEFAULT_TRANSLATION_MODEL,
        "source_language": "en",
        "target_language": "vi",
        "system_prompt": None,
    }.items() <= config["translation"].items()


def test_checked_in_configuration_contains_no_secret_shaped_api_key():
    config = yaml.safe_load(Path("config.yaml").read_text(encoding="utf-8"))
    assert not str(config["translation"]["api_key"]).startswith("sk-")

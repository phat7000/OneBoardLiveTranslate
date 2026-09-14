from pathlib import Path

import yaml

from branding import (
    APP_NAME,
    APP_SHORT_NAME,
    COMPANY_NAME,
    OPEN_SOURCE_NOTICE,
    PRODUCT_NAME,
    PROJECT_LICENSE,
    UPSTREAM_PROJECT_NAME,
    UPSTREAM_PROJECT_URL,
)


def _strings(language: str) -> dict:
    path = Path("i18n") / f"{language}.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_branding_constants():
    assert APP_NAME == "OneBoard Live Translate"
    assert APP_SHORT_NAME == "OneBoardLiveTranslate"
    assert COMPANY_NAME == "OneBoard"
    assert PRODUCT_NAME == APP_NAME
    assert PROJECT_LICENSE == "GPL-3.0-only"
    assert UPSTREAM_PROJECT_NAME == "LiveTranslate"
    assert UPSTREAM_PROJECT_URL == "https://github.com/TheDeathDragon/LiveTranslate"


def test_open_source_notice_exposes_release_licensing_and_attribution():
    assert APP_NAME in OPEN_SOURCE_NOTICE
    assert PROJECT_LICENSE in OPEN_SOURCE_NOTICE
    assert "source code" in OPEN_SOURCE_NOTICE.lower()
    assert "exact matching Git tag" in OPEN_SOURCE_NOTICE
    assert "LICENSES/LiveTranslate-MIT.txt" in OPEN_SOURCE_NOTICE
    assert "THIRD_PARTY_NOTICES.md" in OPEN_SOURCE_NOTICE
    assert UPSTREAM_PROJECT_NAME in OPEN_SOURCE_NOTICE
    assert "MIT attribution" in OPEN_SOURCE_NOTICE


def test_english_product_titles():
    strings = _strings("en")

    assert strings["window_control_panel"] == f"{APP_NAME} - Control Panel"
    assert strings["window_setup"] == f"{APP_NAME} - Initial Setup"
    assert strings["window_download"] == f"{APP_NAME} - Download Models"
    assert strings["window_log"] == f"{APP_NAME} - Log"
    assert strings["tray_tooltip"] == f"{APP_NAME} - Real-time Translation"
    assert f"Restart {APP_NAME}" in strings["mem_warning_msg"]


def test_chinese_product_titles_preserve_localized_text():
    strings = _strings("zh")

    assert strings["window_control_panel"] == f"{APP_NAME} - 控制面板"
    assert strings["window_setup"] == f"{APP_NAME} - 初始设置"
    assert strings["window_download"] == f"{APP_NAME} - 下载模型"
    assert strings["window_log"] == f"{APP_NAME} - 日志"
    assert strings["tray_tooltip"] == f"{APP_NAME} - 实时翻译"
    assert f"重启 {APP_NAME}" in strings["mem_warning_msg"]

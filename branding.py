"""Centralized product branding for the OneBoard distribution."""

from version import VERSION as APP_VERSION, WINDOWS_VERSION as WINDOWS_FILE_VERSION

APP_NAME = "OneBoard Live Translate"
APP_SHORT_NAME = "OneBoardLiveTranslate"
COMPANY_NAME = "OneBoard"
PRODUCT_NAME = "OneBoard Live Translate"
PROJECT_LICENSE = "GPL-3.0-only"
UPSTREAM_PROJECT_NAME = "LiveTranslate"
UPSTREAM_PROJECT_URL = "https://github.com/TheDeathDragon/LiveTranslate"

OPEN_SOURCE_NOTICE = (
    f"{APP_NAME} is free and open-source software licensed under "
    f"{PROJECT_LICENSE}.\n"
    "Corresponding source code is available with each binary release at its "
    "exact matching Git tag.\n"
    "See LICENSE, LICENSES/LiveTranslate-MIT.txt, and THIRD_PARTY_NOTICES.md "
    "in the application folder.\n"
    f"Based on the {UPSTREAM_PROJECT_NAME} open-source project; upstream "
    "copyright and MIT attribution are preserved."
)

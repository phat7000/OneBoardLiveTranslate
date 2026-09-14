"""Writable OneBoard paths without changing source-checkout defaults."""

import os
from pathlib import Path

from branding import APP_SHORT_NAME


def data_dir() -> Path:
    """Keep installed user data outside the application/uninstall directory.

    A developer checkout retains upstream's local state. The distribution marker
    is created only by the release builder; no runtime switch is persisted in
    user settings. An explicit absolute override is useful for portable profiles
    and isolated release QA.
    """
    override = os.environ.get("ONEBOARD_DATA_DIR")
    if override:
        path = Path(override)
        if not path.is_absolute():
            raise ValueError("ONEBOARD_DATA_DIR must be an absolute path")
    elif (Path(__file__).resolve().parent.name == "app"
          and (Path(__file__).resolve().parent.parent / "distribution.json").is_file()):
        local = os.environ.get("LOCALAPPDATA")
        path = (Path(local) if local else Path.home() / "AppData" / "Local") / APP_SHORT_NAME
    else:
        path = Path(__file__).resolve().parent
    path.mkdir(parents=True, exist_ok=True)
    return path

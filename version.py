"""Centralized OneBoard application and Windows release version."""

VERSION = "0.2.0-rc4"
# Windows file versions are numeric; the fourth field maps to release candidate 4.
WINDOWS_VERSION = "0.2.0.4"

# Customer release discovery stays inert until the distributor supplies a real
# OneBoard endpoint. These values must never point at the upstream fork source.
UPDATE_CHANNEL = "stable"
UPDATE_MANIFEST_URL = ""
RELEASE_URL = ""

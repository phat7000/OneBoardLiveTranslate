"""Keep credentials and credential-bearing URLs out of diagnostic output."""

from __future__ import annotations

import logging
import re


_SENSITIVE_FIELD = (
    r"(?:[a-z0-9]+[_-])*(?:credentials?|api[\s_-]?key|access[\s_-]?token|"
    r"refresh[\s_-]?token|authorization|aws[\s_-]?secret[\s_-]?access[\s_-]?key|"
    r"client[\s_-]?assertion|client[\s_-]?secret|account[\s_-]?key|"
    r"https?[\s_-]?proxy|all[\s_-]?proxy|password|private[\s_-]?key|secret|token)"
)
_URL_USERINFO = re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://)[^/@\s]+@")
_SCHEMELESS_USERINFO = re.compile(
    r"(?i)\b[^:/@\s]+:[^/@\s]+@(?=[A-Za-z0-9.-]+(?::\d+)?\b)"
)
_AUTH_VALUE = re.compile(
    r"(?i)\b(Bearer|Basic|Token|ApiKey)\s+[A-Za-z0-9._~+/=:-]{6,}"
)
_PROVIDER_TOKEN = re.compile(
    r"\b(?:sk-[A-Za-z0-9_:\-]{16,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"gh[pousr]_[A-Za-z0-9]{30,}|glpat-[A-Za-z0-9_-]{20,}|"
    r"hf_[A-Za-z0-9]{20,}|npm_[A-Za-z0-9]{20,}|"
    r"xox[baprs]-[0-9A-Za-z-]{20,})\b"
)
_QUOTED_FIELD_VALUE = re.compile(
    rf"(?is)(?P<prefix>[\"']?(?:{_SENSITIVE_FIELD})[\"']?\s*[:=]\s*)"
    r"(?P<quote>[\"'])(?P<value>.*?)(?P=quote)"
)
_UNQUOTED_FIELD_VALUE = re.compile(
    rf"(?i)(?P<prefix>\b(?:{_SENSITIVE_FIELD})\b\s*[:=]\s*)"
    r"(?P<value>[^\s,;&}\]]+)"
)


def redact_sensitive_text(value: object, max_chars: int | None = None) -> str:
    """Return diagnostic text with common secret representations removed."""
    text = str(value)
    text = _URL_USERINFO.sub(r"\1<redacted>@", text)
    text = _SCHEMELESS_USERINFO.sub("<redacted>@", text)
    text = _AUTH_VALUE.sub(r"\1 <redacted>", text)
    text = _QUOTED_FIELD_VALUE.sub(
        lambda match: (
            f'{match.group("prefix")}{match.group("quote")}<redacted>'
            f'{match.group("quote")}'
        ),
        text,
    )
    text = _UNQUOTED_FIELD_VALUE.sub(r"\g<prefix><redacted>", text)
    text = _PROVIDER_TOKEN.sub("<redacted>", text)
    if max_chars is not None and len(text) > max_chars:
        text = text[:max_chars] + "…"
    return text


def safe_exception_text(error: BaseException, max_chars: int = 300) -> str:
    """Create a bounded, single-line, redacted exception description."""
    text = " ".join(str(error).splitlines()).strip()
    return redact_sensitive_text(text or type(error).__name__, max_chars=max_chars)


class RedactingFormatter(logging.Formatter):
    """Apply redaction after logging has rendered messages and tracebacks."""

    def format(self, record: logging.LogRecord) -> str:
        return redact_sensitive_text(super().format(record))

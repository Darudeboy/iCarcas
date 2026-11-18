"""Logging setup with secret redaction filters."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable

_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)(--(?:password|keychain-passphrase|auth-code))([=\s]+)\S+"),
    re.compile(r"(?i)\b(password|passwd|pwd|passphrase|token|cookie|session)\s*[:=]\s*\S+"),
)


def redact_secrets(text: str) -> str:
    redacted = text
    for pattern in _PATTERNS:
        if pattern.pattern.startswith("(?i)(--"):
            redacted = pattern.sub(r"\1=***", redacted)
        else:
            redacted = pattern.sub(lambda m: f"{m.group(1)}=***", redacted)
    return redacted


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_secrets(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: _redact_value(v) for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(_redact_value(a) for a in record.args)
        return True


def _redact_value(value: object) -> object:
    if isinstance(value, str):
        return redact_secrets(value)
    return value


def setup_logging(
    level: int = logging.INFO,
    handlers: Iterable[logging.Handler] | None = None,
) -> None:
    root = logging.getLogger("ios_restore")
    root.setLevel(level)
    root.handlers.clear()
    if handlers is None:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        handlers = (handler,)
    for handler in handlers:
        handler.addFilter(RedactingFilter())
        root.addHandler(handler)

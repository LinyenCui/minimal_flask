import os
import re
from typing import Optional


def mask_value(value: Optional[str], show_start: int = 4, show_end: int = 4) -> str:
    """Mask sensitive string showing first and last few characters.

    Only used for logging/printing. Does not alter the actual value.
    """
    if not value:
        return ""
    value = str(value)
    if len(value) <= show_start + show_end:
        return "*" * len(value)
    return f"{value[:show_start]}{'*' * (len(value) - show_start - show_end)}{value[-show_end:]}"


def mask_db_url(url: Optional[str]) -> str:
    """Mask only the password part in a DB URL (postgres/mysql/etc)."""
    if not url:
        return ""
    # e.g. postgresql://user:pass@host:port/db → mask 'pass'
    return re.sub(r"(://[^:/?#]+:)([^@/]+)(@)", lambda m: m.group(1) + "*" * 8 + m.group(3), str(url))


class MaskSecretsFilter:
    """
    Global logging Filter: masks sensitive env var values appearing in log messages.
    Compares against common key names and replaces their values in log records.
    """

    SENSITIVE_ENV_KEYS = [
        "CHANNEL_ACCESS_TOKEN",
        "CHANNEL_SECRET",
        "OPENAI_API_KEY",
        "GEMINI_API_KEY",
        "DATABASE_URL",
        "LINE_CHANNEL_TOKEN",
        "LINE_CHANNEL_SECRET",
        "RENDER_DATABASE_URL",
    ]

    def __init__(self):
        # Build {raw_value: masked_value} lookup
        self.lookup = {}
        for key in self.SENSITIVE_ENV_KEYS:
            raw_value = os.getenv(key, "")
            if not raw_value:
                continue
            if key in ("DATABASE_URL", "RENDER_DATABASE_URL"):
                self.lookup[raw_value] = mask_db_url(raw_value)
            else:
                self.lookup[raw_value] = mask_value(raw_value)

    def filter(self, record):  # type: ignore[override]
        msg = record.getMessage()
        for raw, masked in self.lookup.items():
            if raw and raw in msg:
                msg = msg.replace(raw, masked)
        record.msg = msg
        record.args = ()
        return True

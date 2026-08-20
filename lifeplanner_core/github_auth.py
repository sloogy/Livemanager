from __future__ import annotations

import os
from pathlib import Path


def github_token() -> str:
    """Return a transient GitHub token without persisting it in LifePlanner.

    Priority: LIFEPLANNER_GITHUB_TOKEN, GITHUB_TOKEN, then a token file named by
    LIFEPLANNER_GITHUB_TOKEN_FILE. The file should be readable only by the user.
    """
    direct = os.environ.get("LIFEPLANNER_GITHUB_TOKEN", "").strip() or os.environ.get("GITHUB_TOKEN", "").strip()
    if direct:
        return direct
    raw_path = os.environ.get("LIFEPLANNER_GITHUB_TOKEN_FILE", "").strip()
    if not raw_path:
        return ""
    path = Path(raw_path).expanduser()
    try:
        stat = path.stat()
        if not path.is_file() or stat.st_size <= 0 or stat.st_size > 16 * 1024:
            return ""
        if os.name != "nt" and stat.st_mode & 0o077:
            return ""
        token = path.read_text(encoding="utf-8").strip()
        return token if "\n" not in token and "\r" not in token else ""
    except (OSError, UnicodeError):
        return ""

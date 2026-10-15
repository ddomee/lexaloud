"""Local storage settings for the optional on-device LLM normalizer.

Lexaloud's speech model is served separately over loopback. This module
contains no model downloader and makes no network requests.
"""

from __future__ import annotations

import os
from pathlib import Path


def default_cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME")
    root = Path(base) if base else Path.home() / ".cache"
    return root / "lexaloud" / "models"


# Bounds the explicit, optional LLM model import command so a malformed local
# source cannot fill the disk. It is not used for speech synthesis.
MAX_MODEL_DOWNLOAD_BYTES: int = 4 * (1 << 30)

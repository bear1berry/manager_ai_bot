from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4


def safe_filename(name: str, extension: str) -> str:
    cleaned = re.sub(r"[^a-zA-Zа-яА-Я0-9_\- ]+", "", name).strip()
    cleaned = re.sub(r"\s+", "_", cleaned)
    if not cleaned:
        cleaned = "document"
    extension = extension.lstrip(".")
    return f"{cleaned}_{uuid4().hex[:8]}.{extension}"


def ensure_dir(path: str | Path) -> Path:
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    return target


def file_size_ok(path: Path, max_bytes: int) -> bool:
    return path.exists() and path.stat().st_size <= max_bytes

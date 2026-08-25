# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
from pathlib import Path
from .config import CACHE_DIR

CACHE_DIR.mkdir(parents=True, exist_ok=True)

def cache_path(namespace: str, key: str, suffix: str = ".bin") -> Path:
    safe_ns = "".join(c for c in namespace if c.isalnum() or c in "-_")
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]
    folder = CACHE_DIR / safe_ns
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{digest}{suffix}"

def get_bytes(namespace: str, key: str):
    p = cache_path(namespace, key)
    return p.read_bytes() if p.exists() else None

def put_bytes(namespace: str, key: str, data: bytes):
    p = cache_path(namespace, key)
    p.write_bytes(data)
    return p

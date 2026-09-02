"""Simple thread-safe in-process TTL cache."""

from __future__ import annotations

import threading
import time
from typing import Any, Hashable


class TtlCache:
    def __init__(self) -> None:
        self._store: dict[Hashable, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: Hashable) -> Any | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if time.monotonic() >= expires_at:
                del self._store[key]
                return None
            return value

    def set(self, key: Hashable, value: Any, ttl_seconds: float) -> None:
        with self._lock:
            self._store[key] = (time.monotonic() + max(ttl_seconds, 0.0), value)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

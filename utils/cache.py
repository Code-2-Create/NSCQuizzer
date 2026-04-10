from __future__ import annotations

import copy
import hashlib
import json
import threading
from pathlib import Path
from typing import Any


class JSONCache:
    _lock = threading.Lock()

    def __init__(self, cache_path: str | Path) -> None:
        self.cache_path = Path(cache_path)
        self._memory_cache: dict[str, Any] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        if self.cache_path.exists():
            try:
                self._memory_cache = json.loads(self.cache_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._memory_cache = {}
        self._loaded = True

    def get(self, key: str) -> Any:
        with self._lock:
            self._ensure_loaded()
            value = self._memory_cache.get(key)
            return copy.deepcopy(value)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._ensure_loaded()
            self._memory_cache[key] = copy.deepcopy(value)
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self.cache_path.with_suffix(".tmp")
            temp_path.write_text(
                json.dumps(self._memory_cache, indent=2, ensure_ascii=True),
                encoding="utf-8",
            )
            temp_path.replace(self.cache_path)


def build_mcq_cache_key(
    chapters: list[str],
    difficulty: str,
    count: int,
    syllabus_context: str,
    pyq_context: str,
    model_name: str,
    variant_tag: str = "",
) -> str:
    fingerprint = hashlib.sha256()
    fingerprint.update("|".join(sorted(chapters)).encode("utf-8"))
    fingerprint.update(difficulty.encode("utf-8"))
    fingerprint.update(str(count).encode("utf-8"))
    fingerprint.update(model_name.encode("utf-8"))
    fingerprint.update(syllabus_context.encode("utf-8"))
    fingerprint.update(pyq_context.encode("utf-8"))
    fingerprint.update(variant_tag.encode("utf-8"))
    return fingerprint.hexdigest()

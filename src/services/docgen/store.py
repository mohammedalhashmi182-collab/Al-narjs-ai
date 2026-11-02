"""Short-lived download tokens. Render's disk is ephemeral, so the files live in memory."""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field

from src.services.docgen.schema import BuiltFile

TTL_SECONDS = 30 * 60
MAX_PACKS = 40


@dataclass
class StoredPack:
    files: dict[str, BuiltFile]
    created: float = field(default_factory=time.monotonic)


class PackStore:
    def __init__(self) -> None:
        self._packs: dict[str, StoredPack] = {}
        self._lock = threading.Lock()

    def put(self, files: list[BuiltFile]) -> str:
        token = uuid.uuid4().hex + uuid.uuid4().hex[:8]
        with self._lock:
            self._purge_locked()
            while len(self._packs) >= MAX_PACKS:
                oldest = min(self._packs, key=lambda key: self._packs[key].created)
                self._packs.pop(oldest, None)
            self._packs[token] = StoredPack(files={item.filename: item for item in files})
        return token

    def get(self, token: str, filename: str) -> BuiltFile | None:
        with self._lock:
            self._purge_locked()
            pack = self._packs.get(token)
            if pack is None:
                return None
            return pack.files.get(filename)

    def reset(self) -> None:
        with self._lock:
            self._packs.clear()

    def _purge_locked(self) -> None:
        now = time.monotonic()
        expired = [key for key, pack in self._packs.items() if now - pack.created > TTL_SECONDS]
        for key in expired:
            self._packs.pop(key, None)


PACKS = PackStore()

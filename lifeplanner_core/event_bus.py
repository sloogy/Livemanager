from __future__ import annotations

import json
import os
import shutil
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import events_dir


@dataclass(frozen=True)
class LifePlannerEvent:
    event_id: str
    schema: str
    event_type: str
    source: str
    occurred_at: str
    profile_id: str
    payload: dict[str, Any]

    @classmethod
    def create(cls, event_type: str, source: str, profile_id: str, payload: dict[str, Any]) -> "LifePlannerEvent":
        if not event_type or not source or not isinstance(payload, dict):
            raise ValueError("Event benötigt event_type, source und ein Payload-Objekt")
        return cls(
            event_id=str(uuid.uuid4()),
            schema="lifeplanner.event.v1",
            event_type=event_type,
            source=source,
            occurred_at=datetime.now(timezone.utc).isoformat(),
            profile_id=profile_id,
            payload=payload,
        )


class FileEventBus:
    """Durable JSONL event bus shared by independent module processes."""

    def __init__(self, profile_id: str):
        self.profile_id = profile_id
        self.path = events_dir(profile_id) / "events.jsonl"
        self.lock_dir = events_dir(profile_id) / ".events.lock"

    def publish(self, event: LifePlannerEvent) -> None:
        if event.profile_id != self.profile_id:
            raise ValueError("Event-Profil passt nicht zum Event-Bus")
        self._acquire_lock()
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            line = json.dumps(asdict(event), ensure_ascii=False, sort_keys=True) + "\n"
            with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(line)
                handle.flush()
                os.fsync(handle.fileno())
        finally:
            self._release_lock()

    def read_since(self, offset: int = 0) -> tuple[list[LifePlannerEvent], int]:
        if not self.path.is_file():
            return [], 0
        events: list[LifePlannerEvent] = []
        with self.path.open("rb") as handle:
            handle.seek(max(0, offset))
            while True:
                vorher = handle.tell()
                raw = handle.readline()
                if not raw:
                    break
                if not raw.endswith(b"\n"):
                    # Die letzte Zeile ist noch nicht fertig geschrieben. Sie
                    # jetzt zu verwerfen und den Offset dahinter zu setzen
                    # hiesse, ihren Anfang endgueltig zu verlieren: Der
                    # Schreiber haengt gleich den Rest an, und der waere dann
                    # eine Zeile ohne Anfang. Also hier stehen bleiben und
                    # beim naechsten Mal von vorn lesen.
                    handle.seek(vorher)
                    break
                try:
                    obj = json.loads(raw.decode("utf-8"))
                    if obj.get("schema") != "lifeplanner.event.v1":
                        continue
                    events.append(LifePlannerEvent(**obj))
                except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
                    continue
            new_offset = handle.tell()
        return events, new_offset

    def _acquire_lock(self, timeout: float = 3.0) -> None:
        deadline = time.monotonic() + timeout
        while True:
            try:
                self.lock_dir.mkdir()
                (self.lock_dir / "owner").write_text(str(os.getpid()), encoding="ascii")
                return
            except FileExistsError:
                try:
                    age = time.time() - self.lock_dir.stat().st_mtime
                    if age > 30:
                        shutil.rmtree(self.lock_dir, ignore_errors=True)
                        continue
                except OSError:
                    pass
                if time.monotonic() >= deadline:
                    raise TimeoutError("Event-Bus ist vorübergehend gesperrt")
                time.sleep(0.05)

    def _release_lock(self) -> None:
        shutil.rmtree(self.lock_dir, ignore_errors=True)

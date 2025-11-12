from __future__ import annotations

import uuid
from pathlib import Path
from typing import Iterable, List, Tuple

from fastapi import UploadFile

from ehs_ai.schemas import EvidenceItem
from ehs_ai.utils.logger import get_logger

logger = get_logger(__name__)


class EvidenceStorage:
    """Handles persistent storage of incident evidence files."""

    def __init__(self, root: Path | None = None, max_bytes: int = 5 * 1024 * 1024) -> None:
        self._root = root or Path("./storage/evidence")
        self._root.mkdir(parents=True, exist_ok=True)
        self._max_bytes = max_bytes

    @property
    def root(self) -> Path:
        return self._root

    async def save(self, *, incident_id: str, files: Iterable[UploadFile]) -> List[Tuple[EvidenceItem, str]]:
        records: List[Tuple[EvidenceItem, str]] = []
        incident_dir = self._root / incident_id
        incident_dir.mkdir(parents=True, exist_ok=True)

        for upload in files:
            size, rel_name = await self._write_file(incident_dir, upload)
            if size is None:
                continue
            item = EvidenceItem(
                filename=upload.filename or rel_name,
                url=f"/evidence/{incident_id}/{rel_name}",
                size_bytes=size,
            )
            records.append((item, rel_name))
        return records

    def resolve(self, incident_id: str, filename: str) -> Path:
        return (self._root / incident_id / filename).resolve()

    async def _write_file(self, incident_dir: Path, upload: UploadFile) -> tuple[int | None, str]:
        filename = upload.filename or "evidence"
        sanitized = _sanitize_filename(filename)
        unique_name = f"{uuid.uuid4().hex}_{sanitized}"
        target_path = incident_dir / unique_name

        total = 0
        try:
            with target_path.open("wb") as buffer:
                while True:
                    chunk = await upload.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > self._max_bytes:
                        logger.warning("Evidence file %s exceeds size limit; skipping save.", filename)
                        await upload.close()
                        target_path.unlink(missing_ok=True)
                        return None, unique_name
                    buffer.write(chunk)
        finally:
            await upload.close()

        return total, unique_name


def _sanitize_filename(name: str) -> str:
    allowed = [ch if ch.isalnum() or ch in {".", "-", "_"} else "_" for ch in name]
    sanitized = "".join(allowed).strip("._")
    return sanitized or "evidence"

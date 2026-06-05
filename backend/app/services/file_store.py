"""Filesystem layout for job inputs/outputs."""
from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path


class FileStore:
    """Manages per-job directories under a single root."""

    def __init__(self, root: str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def new_job_dir(self) -> tuple[str, str]:
        """Create a new per-job directory. Returns (job_id, absolute_path)."""
        jid = uuid.uuid4().hex
        d = self.root / jid
        d.mkdir(parents=False, exist_ok=False)
        return jid, str(d)

    def path(self, job_id: str, name: str) -> str:
        return str(self.root / job_id / name)

    def delete_job(self, job_id: str) -> None:
        d = self.root / job_id
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)

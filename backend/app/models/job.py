"""Domain enums and DTOs for the job lifecycle and progress reporting."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Literal, Optional


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELED = "canceled"


StageName = Literal["tiling", "inference", "blending", "encoding"]


@dataclass(frozen=True)
class ProgressEvent:
    """Emitted by Pipeline.run() to report progress to JobManager."""
    stage: StageName
    current: int
    total: int


@dataclass
class Job:
    """Persistent record of an upscaling job."""
    id: str
    status: JobStatus
    stage: Optional[str]
    progress: float
    scale: int
    input_path: str
    output_path: Optional[str]
    error: Optional[str]
    created_at: datetime
    updated_at: datetime

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        d["createdAt"] = self.created_at.isoformat()
        d["updatedAt"] = self.updated_at.isoformat()
        return d

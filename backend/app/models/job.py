"""Domain enums and DTOs for the job lifecycle and progress reporting."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal


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

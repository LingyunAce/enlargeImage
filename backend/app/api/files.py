"""Output file download route."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from app.services.job_manager import JobManager

router = APIRouter(prefix="/api/jobs", tags=["files"])


def get_jm(request: Request) -> JobManager:
    return request.app.state.job_manager


@router.get("/{job_id}/output")
async def get_output(job_id: str, jm: JobManager = Depends(get_jm)):
    job = jm.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"error": "not_found"})
    if job.status.value != "done" or not job.output_path:
        raise HTTPException(
            status_code=409,
            detail={"error": "not_ready", "status": job.status.value},
        )
    from pathlib import Path
    p = Path(job.output_path)
    if not p.exists():
        raise HTTPException(status_code=410, detail={"error": "output_missing"})
    return FileResponse(
        path=str(p),
        media_type="image/png",
        filename=f"enlarged-{job_id}.png",
    )

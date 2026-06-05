"""HTTP routes for job lifecycle."""
from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse

from app.models.job import Job, JobStatus
from app.services.job_manager import JobManager

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


# --- DI: JobManager is stored on app.state at startup ---
def get_jm(request: Request) -> JobManager:
    return request.app.state.job_manager


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_job(
    file: UploadFile = File(...),
    scale: int = Form(...),
    jm: JobManager = Depends(get_jm),
) -> dict:
    # Validate scale
    settings = jm.store  # not really — use jm's settings via app
    # We read settings from app.state to keep things explicit
    from app.config import get_settings
    s = get_settings()
    if scale not in s.supported_scales:
        raise HTTPException(status_code=400, detail={
            "error": "unsupported_scale", "scale": scale,
            "allowed": list(s.supported_scales),
        })

    # Validate format
    ext = (file.filename or "").rsplit(".", 1)[-1].lower()
    if ext not in s.supported_input_formats:
        raise HTTPException(status_code=415, detail={
            "error": "unsupported_format", "got": ext,
        })

    # Read body with size cap
    body = await file.read()
    if len(body) > s.max_input_bytes:
        raise HTTPException(status_code=413, detail={
            "error": "file_too_large", "max_bytes": s.max_input_bytes,
        })

    # Decode
    try:
        from PIL import Image
        import io as _io
        im = Image.open(_io.BytesIO(body))
        im.load()
        if im.mode != "RGB":
            im = im.convert("RGB")
        w, h = im.size
    except Exception:
        raise HTTPException(status_code=400, detail={"error": "decode_failed"})

    if w * h > s.max_input_pixels:
        raise HTTPException(status_code=413, detail={
            "error": "image_too_large", "max_pixels": s.max_input_pixels,
            "got_pixels": w * h,
        })

    # Persist input to disk
    jid, _ = jm.file_store.new_job_dir()
    input_path = jm.file_store.path(jid, "input.png")
    im.save(input_path, format="PNG")

    # Create job
    from datetime import timezone
    now = datetime.now(timezone.utc)
    job = Job(
        id=jid, status=JobStatus.QUEUED, stage=None, progress=0.0,
        scale=scale, input_path=input_path, output_path=None, error=None,
        created_at=now, updated_at=now,
    )
    jm._cache[jid] = job
    jm.store.upsert(job)
    jm._tasks[jid] = __import__("asyncio").create_task(jm._run_job(job))
    jm._tasks[jid].set_name(f"job-{jid}")
    jm._wake_next.set()
    return job.to_dict()


@router.get("")
async def list_jobs(limit: int = 20, jm: JobManager = Depends(get_jm)) -> list[dict]:
    return [j.to_dict() for j in jm.list_recent(limit=limit)]


@router.get("/{job_id}")
async def get_job(job_id: str, jm: JobManager = Depends(get_jm)) -> dict:
    job = jm.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"error": "not_found"})
    return job.to_dict()


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(job_id: str, jm: JobManager = Depends(get_jm)):
    ok = await jm.delete(job_id)
    if not ok:
        raise HTTPException(status_code=404, detail={"error": "not_found"})

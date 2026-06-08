"""HTTP routes for job lifecycle."""
from __future__ import annotations

import asyncio
import io
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError

from app.api.deps import get_jm
from app.services.job_manager import JobManager

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


class _TooLarge(Exception):
    pass


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_job(
    file: UploadFile = File(...),
    scale: int = Form(...),
    jm: JobManager = Depends(get_jm),
) -> dict:
    # Validate scale
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

    # Decode + save to disk in a worker thread (CPU/IO bound)
    try:
        def _decode_and_save():
            im = Image.open(io.BytesIO(body))
            im.load()
            if im.mode != "RGB":
                im = im.convert("RGB")
            w, h = im.size
            if w * h > s.max_input_pixels:
                raise _TooLarge(f"{w * h} > {s.max_input_pixels}")
            jid, _ = jm.file_store.new_job_dir()
            input_path = jm.file_store.path(jid, "input.png")
            im.save(input_path, format="PNG")
            return jid, input_path, (w, h)
        loop = asyncio.get_event_loop()
        jid, input_path, (w, h) = await loop.run_in_executor(None, _decode_and_save)
    except _TooLarge:
        raise HTTPException(status_code=413, detail={
            "error": "image_too_large", "max_pixels": s.max_input_pixels,
            "got_pixels": w * h,
        })
    except UnidentifiedImageError as e:
        log.warning("UnidentifiedImageError: %s", e)
        raise HTTPException(status_code=400, detail={
            "error": "unsupported_image",
            "message": "File is not a recognized image. Use PNG, JPEG, or WebP.",
        })
    except (OSError, ValueError) as e:
        # PIL raises these for truncated / corrupt files
        log.warning("Corrupt or truncated image: %s", e)
        raise HTTPException(status_code=400, detail={
            "error": "corrupt_image",
            "message": "Image file appears to be corrupt or truncated. Try re-saving it.",
        })
    except Exception:
        # Truly unexpected — log full traceback for debugging
        log.exception("Unexpected error during image decode/save")
        raise HTTPException(status_code=400, detail={"error": "decode_failed"})

    # Create job
    job = await jm.create(input_path=input_path, scale=scale, jid=jid)
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

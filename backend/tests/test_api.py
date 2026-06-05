import io
import time
from PIL import Image
import pytest


def _png_bytes(w: int, h: int, color=(255, 0, 0)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, format="PNG")
    return buf.getvalue()


def test_health(app_with_fake_runner):
    client, _ = app_with_fake_runner
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_create_then_get_then_output(app_with_fake_runner):
    client, _ = app_with_fake_runner
    r = client.post(
        "/api/jobs",
        files={"file": ("in.png", _png_bytes(50, 50), "image/png")},
        data={"scale": "2"},
    )
    assert r.status_code == 201, r.text
    job = r.json()
    jid = job["id"]
    assert job["status"] in ("queued", "running")

    # Poll until done (max 5s)
    deadline = time.time() + 5
    while time.time() < deadline:
        r = client.get(f"/api/jobs/{jid}")
        if r.json()["status"] == "done":
            break
        time.sleep(0.05)
    assert r.json()["status"] == "done", r.json()

    # Output
    r = client.get(f"/api/jobs/{jid}/output")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/png")
    assert len(r.content) > 0


def test_list_recent(app_with_fake_runner):
    client, _ = app_with_fake_runner
    for _ in range(2):
        client.post(
            "/api/jobs",
            files={"file": ("in.png", _png_bytes(40, 40), "image/png")},
            data={"scale": "2"},
        )
    r = client.get("/api/jobs")
    assert r.status_code == 200
    assert len(r.json()) >= 2


def test_create_rejects_unsupported_format(app_with_fake_runner):
    client, _ = app_with_fake_runner
    r = client.post(
        "/api/jobs",
        files={"file": ("in.gif", b"GIF89a", "image/gif")},
        data={"scale": "2"},
    )
    assert r.status_code == 415


def test_create_rejects_oversize(app_with_fake_runner):
    client, _ = app_with_fake_runner
    # 21 MB of zeros
    big = b"\x00" * (21 * 1024 * 1024)
    r = client.post(
        "/api/jobs",
        files={"file": ("in.png", big, "image/png")},
        data={"scale": "2"},
    )
    assert r.status_code == 413


def test_output_not_ready_returns_409(app_with_fake_runner):
    client, _ = app_with_fake_runner
    # Manually insert a queued job via the job manager
    _, jm = app_with_fake_runner
    from app.models.job import Job, JobStatus
    from datetime import datetime, timezone
    jid, _ = jm.file_store.new_job_dir()
    jm._cache[jid] = Job(
        id=jid, status=JobStatus.QUEUED, stage=None, progress=0.0,
        scale=2, input_path="x", output_path=None, error=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    jm.store.upsert(jm._cache[jid])
    r = client.get(f"/api/jobs/{jid}/output")
    assert r.status_code == 409


def test_delete_removes_job(app_with_fake_runner):
    client, _ = app_with_fake_runner
    r = client.post(
        "/api/jobs",
        files={"file": ("in.png", _png_bytes(40, 40), "image/png")},
        data={"scale": "2"},
    )
    jid = r.json()["id"]
    # Wait for done
    deadline = time.time() + 5
    while time.time() < deadline:
        r = client.get(f"/api/jobs/{jid}")
        if r.json()["status"] == "done":
            break
        time.sleep(0.05)
    r = client.delete(f"/api/jobs/{jid}")
    assert r.status_code == 204
    r = client.get(f"/api/jobs/{jid}")
    assert r.status_code == 404

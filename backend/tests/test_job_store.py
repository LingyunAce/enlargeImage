import pytest
from datetime import datetime, timezone
from app.models.job import Job, JobStatus
from app.services.job_store import JobStore


@pytest.fixture
def store(tmp_path):
    return JobStore(db_path=str(tmp_path / "test.db"))


def _make_job(jid: str, created: datetime, status=JobStatus.QUEUED) -> Job:
    return Job(
        id=jid, status=status, stage=None, progress=0.0,
        scale=4, input_path=f"/tmp/{jid}.png", output_path=None, error=None,
        created_at=created, updated_at=created,
    )


def test_upsert_then_get(store: JobStore):
    j = _make_job("j1", datetime(2026, 1, 1, tzinfo=timezone.utc))
    store.upsert(j)
    got = store.get("j1")
    assert got is not None
    assert got.id == "j1"
    assert got.status is JobStatus.QUEUED
    assert got.scale == 4


def test_get_missing_returns_none(store: JobStore):
    assert store.get("nope") is None


def test_upsert_overwrites_existing(store: JobStore):
    j = _make_job("j1", datetime(2026, 1, 1, tzinfo=timezone.utc))
    store.upsert(j)
    j2 = _make_job("j1", datetime(2026, 1, 1, tzinfo=timezone.utc), status=JobStatus.RUNNING)
    j2.progress = 0.5
    store.upsert(j2)
    got = store.get("j1")
    assert got.status is JobStatus.RUNNING
    assert got.progress == 0.5


def test_delete_removes_row(store: JobStore):
    j = _make_job("j1", datetime(2026, 1, 1, tzinfo=timezone.utc))
    store.upsert(j)
    store.delete("j1")
    assert store.get("j1") is None

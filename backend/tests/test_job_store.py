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


def test_list_recent_returns_newest_first(store: JobStore):
    j1 = _make_job("j1", datetime(2026, 1, 1, tzinfo=timezone.utc))
    j2 = _make_job("j2", datetime(2026, 1, 2, tzinfo=timezone.utc))
    j3 = _make_job("j3", datetime(2026, 1, 3, tzinfo=timezone.utc))
    for j in [j1, j2, j3]:
        store.upsert(j)
    recent = store.list_recent(10)
    assert [j.id for j in recent] == ["j3", "j2", "j1"]


def test_list_recent_respects_limit(store: JobStore):
    for i in range(5):
        store.upsert(_make_job(f"j{i}", datetime(2026, 1, i + 1, tzinfo=timezone.utc)))
    recent = store.list_recent(2)
    assert len(recent) == 2
    assert recent[0].id == "j4"


def test_list_ids_older_than_excludes_newest(store: JobStore):
    for i in range(5):
        store.upsert(_make_job(f"j{i}", datetime(2026, 1, i + 1, tzinfo=timezone.utc)))
    old = store.list_ids_older_than(keep=2)
    assert sorted(old) == ["j0", "j1", "j2"]


def test_mark_stale_as_failed_changes_queued_and_running(store: JobStore):
    store.upsert(_make_job("a", datetime(2026, 1, 1, tzinfo=timezone.utc), status=JobStatus.QUEUED))
    store.upsert(_make_job("b", datetime(2026, 1, 1, tzinfo=timezone.utc), status=JobStatus.RUNNING))
    store.upsert(_make_job("c", datetime(2026, 1, 1, tzinfo=timezone.utc), status=JobStatus.DONE))
    n = store.mark_stale_as_failed("server_restart")
    assert n == 2
    a = store.get("a")
    b = store.get("b")
    c = store.get("c")
    assert a.status is JobStatus.FAILED and a.error == "server_restart"
    assert b.status is JobStatus.FAILED and b.error == "server_restart"
    assert c.status is JobStatus.DONE  # untouched

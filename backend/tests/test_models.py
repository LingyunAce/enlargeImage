from datetime import datetime, timezone
from app.models.job import Job, JobStatus, ProgressEvent


def test_job_status_values():
    assert JobStatus.QUEUED.value == "queued"
    assert JobStatus.RUNNING.value == "running"
    assert JobStatus.DONE.value == "done"
    assert JobStatus.FAILED.value == "failed"
    assert JobStatus.CANCELED.value == "canceled"


def test_job_status_is_str():
    # StrEnum-like behavior: serializes to its value as a plain string
    assert str(JobStatus.QUEUED) == "JobStatus.QUEUED"
    assert JobStatus("queued") is JobStatus.QUEUED


def test_progress_event_constructs():
    ev = ProgressEvent(stage="inference", current=3, total=10)
    assert ev.stage == "inference"
    assert ev.current == 3
    assert ev.total == 10


def test_job_constructs_with_required_fields():
    now = datetime.now(timezone.utc)
    j = Job(
        id="abc",
        status=JobStatus.QUEUED,
        stage=None,
        progress=0.0,
        scale=4,
        input_path="/tmp/in.png",
        output_path=None,
        error=None,
        created_at=now,
        updated_at=now,
    )
    assert j.id == "abc"
    assert j.status is JobStatus.QUEUED
    assert j.progress == 0.0


def test_job_to_dict_serializes_status_as_string():
    now = datetime.now(timezone.utc)
    j = Job(
        id="x", status=JobStatus.RUNNING, stage="inference", progress=0.5,
        scale=2, input_path="a", output_path=None, error=None,
        created_at=now, updated_at=now,
    )
    d = j.to_dict()
    assert d["status"] == "running"
    assert d["stage"] == "inference"
    assert d["progress"] == 0.5
    assert d["scale"] == 2
    assert d["createdAt"] == now.isoformat()

from app.models.job import JobStatus, ProgressEvent


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

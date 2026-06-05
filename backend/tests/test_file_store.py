import pytest
from pathlib import Path
from app.services.file_store import FileStore


@pytest.fixture
def fs(tmp_path: Path) -> FileStore:
    return FileStore(root=str(tmp_path))


def test_new_job_dir_creates_unique_ids(fs: FileStore, tmp_path: Path):
    a_id, a_path = fs.new_job_dir()
    b_id, b_path = fs.new_job_dir()
    assert a_id != b_id
    assert (tmp_path / a_id).is_dir()
    assert (tmp_path / b_id).is_dir()


def test_path_returns_path_under_job_dir(fs: FileStore, tmp_path: Path):
    jid, _ = fs.new_job_dir()
    p = fs.path(jid, "input.png")
    assert p == str(tmp_path / jid / "input.png")


def test_delete_job_removes_directory(fs: FileStore, tmp_path: Path):
    jid, _ = fs.new_job_dir()
    (tmp_path / jid / "input.png").write_text("x")
    fs.delete_job(jid)
    assert not (tmp_path / jid).exists()

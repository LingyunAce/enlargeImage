"""SQLite-backed persistence for Job records.

Sync throughout: the JobManager flush loop and API handlers both need low
overhead, single-writer access without asyncio ceremony. Schema is created
synchronously on first construction; the file is reused on subsequent runs.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.models.job import Job, JobStatus


_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    stage TEXT,
    progress REAL NOT NULL,
    scale INTEGER NOT NULL,
    input_path TEXT NOT NULL,
    output_path TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

_CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at);
"""


def _row_to_job(row: sqlite3.Row) -> Job:
    return Job(
        id=row["id"],
        status=JobStatus(row["status"]),
        stage=row["stage"],
        progress=row["progress"],
        scale=row["scale"],
        input_path=row["input_path"],
        output_path=row["output_path"],
        error=row["error"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


class JobStore:
    """Owns a single SQLite file. Single-writer by convention."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        new = not Path(db_path).exists()
        conn = sqlite3.connect(db_path)
        try:
            conn.row_factory = sqlite3.Row
            if new:
                conn.executescript(_CREATE_SQL + _CREATE_INDEX_SQL)
                conn.commit()
        finally:
            conn.close()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def upsert(self, job: Job) -> None:
        """Insert or replace a job row by primary key."""
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO jobs (id, status, stage, progress, scale, input_path,
                                  output_path, error, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status=excluded.status,
                    stage=excluded.stage,
                    progress=excluded.progress,
                    scale=excluded.scale,
                    input_path=excluded.input_path,
                    output_path=excluded.output_path,
                    error=excluded.error,
                    updated_at=excluded.updated_at
                """,
                (
                    job.id, job.status.value, job.stage, job.progress, job.scale,
                    job.input_path, job.output_path, job.error,
                    job.created_at.isoformat(), job.updated_at.isoformat(),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get(self, job_id: str) -> Optional[Job]:
        conn = self._connect()
        try:
            cur = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
            row = cur.fetchone()
            return _row_to_job(row) if row else None
        finally:
            conn.close()

    def delete(self, job_id: str) -> None:
        conn = self._connect()
        try:
            conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
            conn.commit()
        finally:
            conn.close()

    def list_recent(self, limit: int) -> list[Job]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
            )
            rows = cur.fetchall()
            return [_row_to_job(r) for r in rows]
        finally:
            conn.close()

    def list_ids_older_than(self, keep: int) -> list[str]:
        """Return job_ids of rows beyond the newest `keep`, ordered oldest first."""
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute(
                """
                SELECT id FROM jobs
                ORDER BY created_at DESC
                LIMIT -1 OFFSET ?
                """,
                (keep,),
            )
            rows = cur.fetchall()
            # Rows are newest-first; reverse to oldest-first for caller convenience
            return [r[0] for r in reversed(rows)]
        finally:
            conn.close()

    def mark_stale_as_failed(self, reason: str) -> int:
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.execute(
                """
                UPDATE jobs
                SET status = ?, error = ?, updated_at = ?
                WHERE status IN (?, ?)
                """,
                (
                    JobStatus.FAILED.value,
                    reason,
                    datetime.now().astimezone().isoformat(),
                    JobStatus.QUEUED.value,
                    JobStatus.RUNNING.value,
                ),
            )
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()

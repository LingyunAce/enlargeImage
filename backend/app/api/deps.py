"""Shared FastAPI dependencies."""
from fastapi import Request

from app.services.job_manager import JobManager


def get_jm(request: Request) -> JobManager:
    return request.app.state.job_manager

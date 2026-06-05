"""Application configuration. Single source of truth for tunables."""
from __future__ import annotations

from functools import lru_cache

from pydantic import BaseModel, ConfigDict, Field


class Settings(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_dir: str
    storage_dir: str
    db_path: str
    log_level: str = "INFO"

    # Pipeline
    tile_size: int = 192
    overlap: int = 24
    supported_scales: tuple[int, ...] = (2, 4, 8)

    # Input limits
    supported_input_formats: list[str] = Field(
        default_factory=lambda: ["png", "jpg", "jpeg", "webp"]
    )
    max_input_pixels: int = 2000 * 2000
    max_input_bytes: int = 20 * 1024 * 1024

    # Job manager
    history_keep: int = 20
    flush_interval: float = 0.5
    semaphore_permits: int = 1


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a process-wide singleton Settings built from env (with defaults)."""
    import os
    return Settings(
        model_dir=os.getenv("MODEL_DIR", "./models"),
        storage_dir=os.getenv("STORAGE_DIR", "./storage"),
        db_path=os.getenv("DB_PATH", "./data.db"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )

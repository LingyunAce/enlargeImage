import pytest
from app.config import Settings, get_settings


def test_settings_defaults():
    s = Settings(
        model_dir="./models",
        storage_dir="./storage",
        db_path="./data.db",
    )
    assert s.tile_size == 192
    assert s.overlap == 24
    assert s.supported_input_formats == ["png", "jpg", "jpeg", "webp"]
    assert s.max_input_pixels == 2000 * 2000
    assert s.max_input_bytes == 20 * 1024 * 1024
    assert s.history_keep == 20
    assert s.flush_interval == 0.5
    assert s.semaphore_permits == 1


def test_get_settings_returns_singleton():
    a = get_settings()
    b = get_settings()
    assert a is b


def test_supported_scale():
    s = Settings(
        model_dir="./models",
        storage_dir="./storage",
        db_path="./data.db",
    )
    assert s.supported_scales == (2, 4, 8)

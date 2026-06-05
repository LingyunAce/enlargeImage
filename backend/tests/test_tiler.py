import numpy as np
import pytest
from app.pipeline.tiler import Tiler, TileRequest


@pytest.fixture
def tiler() -> Tiler:
    return Tiler(tile_size=192, overlap=24)


def test_split_even_dimensions_yields_uniform_tiles(tiler: Tiler):
    # 384 = 2 * (192 - 24) + 24 = 336 + 48, no — recalc:
    # step = 192 - 24 = 168. For W=512: 0..192, 168..360, 336..504, 504..512 (clipped to 512, w=8)
    # Better: use W = 192 + 168 + 168 = 528? No. Use W=384: tiles 0..192, 168..360, 336..384(w=48)
    img = np.zeros((100, 384, 3), dtype=np.uint8)
    tiles = tiler.split(img, scale=2)
    # Tiles in y: only 1 (H=100 < 192, so y=0, h=100, w=384... wait that's whole width)
    # Actually with H=100, tiler produces one tile covering full height
    # Width: step=168, start positions 0, 168, 336, then last 384-336=48
    assert len(tiles) == 4
    assert tiles[0].x == 0 and tiles[0].w == 192
    assert tiles[1].x == 168 and tiles[1].w == 192
    assert tiles[2].x == 336 and tiles[2].w == 48  # clipped to remaining


def test_expected_count_matches_split(tiler: Tiler):
    img = np.zeros((300, 500, 3), dtype=np.uint8)
    actual = tiler.split(img, scale=4)
    expected = tiler.expected_count(h=300, w=500)
    assert len(actual) == expected


def test_small_image_yields_single_tile(tiler: Tiler):
    img = np.zeros((50, 50, 3), dtype=np.uint8)
    tiles = tiler.split(img, scale=4)
    assert len(tiles) == 1
    assert tiles[0].x == 0 and tiles[0].y == 0
    assert tiles[0].w == 50 and tiles[0].h == 50
    assert tiles[0].out_w == 200 and tiles[0].out_h == 200


def test_tile_request_is_frozen():
    r = TileRequest(x=0, y=0, w=100, h=100, out_w=400, out_h=400)
    with pytest.raises(Exception):  # FrozenInstanceError
        r.x = 5  # type: ignore


def test_split_uses_step_tile_size_minus_overlap(tiler: Tiler):
    # With overlap=24 and tile_size=192, step = 168
    # W = 192 + 168 = 360 should give exactly 2 full tiles
    img = np.zeros((100, 360, 3), dtype=np.uint8)
    tiles = tiler.split(img, scale=1)
    assert len(tiles) == 2
    assert tiles[0].x == 0 and tiles[0].w == 192
    assert tiles[1].x == 168 and tiles[1].w == 192

import numpy as np
from app.pipeline.seam import SeamBlender
from app.pipeline.tiler import TileRequest


def _req(x, y, w, h, scale=1):
    return TileRequest(x=x, y=y, w=w, h=h, out_w=w * scale, out_h=h * scale)


def test_single_tile_passes_through_unchanged():
    img = np.random.randint(0, 256, (50, 50, 3), dtype=np.uint8)
    out = SeamBlender().blend([(_req(0, 0, 50, 50), img)], canvas_h=50, canvas_w=50)
    np.testing.assert_array_equal(out, img)


def test_two_horizontally_adjacent_tiles_no_gap():
    # Tile A: red  (x=0..50), Tile B: green (x=50..100), no overlap
    a = np.full((20, 50, 3), [255, 0, 0], dtype=np.uint8)
    b = np.full((20, 50, 3), [0, 255, 0], dtype=np.uint8)
    out = SeamBlender().blend(
        [(_req(0, 0, 50, 20), a), (_req(50, 0, 50, 20), b)],
        canvas_h=20, canvas_w=100,
    )
    # Left half red, right half green, exact transition at x=50
    assert np.all(out[:, 0:50, :] == [255, 0, 0])
    assert np.all(out[:, 50:100, :] == [0, 255, 0])


def test_two_overlapping_tiles_blend_smoothly():
    # A covers x=0..60 (60 wide), B covers x=40..100 (60 wide), overlap x=40..60
    a = np.full((20, 60, 3), [255, 0, 0], dtype=np.uint8)
    b = np.full((20, 60, 3), [0, 255, 0], dtype=np.uint8)
    out = SeamBlender().blend(
        [(_req(0, 0, 60, 20), a), (_req(40, 0, 60, 20), b)],
        canvas_h=20, canvas_w=100,
    )
    # Outside overlap, colors are pure. Inside overlap (x=40..60), they should blend.
    assert np.all(out[10, 0, :] == [255, 0, 0])      # pure red left
    assert np.all(out[10, 99, :] == [0, 255, 0])     # pure green right
    # At the very center of overlap (x=50), channels should be roughly half-half
    center = out[10, 50, :]
    assert 100 < center[0] < 160  # red between min and max
    assert 100 < center[1] < 160  # green between min and max


def test_four_tile_grid_no_seam_artifacts():
    # Build a diagonal gradient input, split into 4 overlapping tiles,
    # verify the reconstructed canvas matches the original gradient
    h, w = 100, 100
    orig = np.zeros((h, w, 3), dtype=np.uint8)
    for i in range(h):
        orig[i, :, 0] = i * 2  # red ramps down rows
        orig[i, :, 1] = 128
        orig[i, :, 2] = 50
    # Each tile is 60x60, overlap 20. Positions: (0,0), (0,40), (40,0), (40,40)
    tiles = []
    for y in [0, 40]:
        for x in [0, 40]:
            crop = orig[y:y + 60, x:x + 60, :].copy()
            tiles.append((_req(x, y, 60, 60), crop))
    out = SeamBlender().blend(tiles, canvas_h=h, canvas_w=w)
    # Allow tiny rounding error from uint8 conversion of accumulated weights
    diff = np.abs(out.astype(np.int16) - orig.astype(np.int16))
    assert diff.max() <= 2  # ±2 LSB max — visually invisible

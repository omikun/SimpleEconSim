import time, pygame
from hexmap import rectangular_hex_layout, hex_bbox
from worldview_camera import HEX_SIZE
from render_dev_viewer import create_mock_island_tiles
from render_engine.gpu import get_gpu_pipeline
from polygon_map import apply_polygon_map_to_world

pipeline = get_gpu_pipeline()

for dim in [9, 13, 17]:
    t0 = time.time()
    layout = rectangular_hex_layout(dim, dim)
    bbox = hex_bbox(layout, HEX_SIZE)
    tiles = create_mock_island_tiles(seed=777, rows=dim, cols=dim)
    gen = apply_polygon_map_to_world(tiles, seed=777, grid_rows=dim, grid_cols=dim, num_points=1200)
    surf = pipeline.render_topographic_surface(
        seed=777,
        bbox=bbox,
        tiles=tiles,
        layout=layout,
        width=2048,
        height=2048,
        uniforms={'sun_azimuth': -135.0, 'sun_elevation': 42.0, 'sun_intensity': 1.15}
    )
    fname = f"scratch/test_gpu_grid_{dim}x{dim}.png"
    pygame.image.save(surf, fname)
    print(f"Dim {dim}x{dim}: time={time.time() - t0:.3f}s, saved {fname}")

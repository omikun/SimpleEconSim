import time, pygame
from hexmap import rectangular_hex_layout, hex_bbox
from worldview_camera import HEX_SIZE
from render_dev_viewer import create_mock_island_tiles
from render_engine.gpu import get_gpu_pipeline
from polygon_map import apply_polygon_map_to_world

pipeline = get_gpu_pipeline()
dim = 13
layout = rectangular_hex_layout(dim, dim)
bbox = hex_bbox(layout, HEX_SIZE)
tiles = create_mock_island_tiles(seed=777, rows=dim, cols=dim)
gen = apply_polygon_map_to_world(tiles, seed=777, grid_rows=dim, grid_cols=dim, num_points=1200)

# Render with morning sun (azimuth -45, elevation 25)
surf_morning = pipeline.render_topographic_surface(
    seed=777, bbox=bbox, tiles=tiles, layout=layout, width=1024, height=1024,
    uniforms={'sun_azimuth': -45.0, 'sun_elevation': 25.0, 'sun_intensity': 1.25}
)
pygame.image.save(surf_morning, "scratch/sun_morning.png")

# Render with afternoon / game default sun (azimuth -135, elevation 42)
surf_afternoon = pipeline.render_topographic_surface(
    seed=777, bbox=bbox, tiles=tiles, layout=layout, width=1024, height=1024,
    uniforms={'sun_azimuth': -135.0, 'sun_elevation': 42.0, 'sun_intensity': 1.15}
)
pygame.image.save(surf_afternoon, "scratch/sun_afternoon.png")

# Render with sunset low golden sun (azimuth 110, elevation 15)
surf_sunset = pipeline.render_topographic_surface(
    seed=777, bbox=bbox, tiles=tiles, layout=layout, width=1024, height=1024,
    uniforms={'sun_azimuth': 110.0, 'sun_elevation': 15.0, 'sun_intensity': 1.35}
)
pygame.image.save(surf_sunset, "scratch/sun_sunset.png")
print("Saved sun angle comparison images.")

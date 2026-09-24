import numpy as np
import time
import pygame
import os

os.environ['SDL_AUDIODRIVER'] = 'dummy'
os.environ['SDL_VIDEODRIVER'] = 'dummy'
pygame.init()
surf = pygame.Surface((1000, 1000))

t0 = time.time()
for _ in range(25000):
    pts = [(int(np.random.randint(0, 1000)), int(np.random.randint(0, 1000))) for _ in range(3)]
    col = (120, 150, 100)
    pygame.draw.polygon(surf, col, pts)
t1 = time.time()
print(f"Drawing 25,000 triangles took {(t1 - t0)*1000:.2f} ms")

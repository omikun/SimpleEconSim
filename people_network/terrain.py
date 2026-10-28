"""Read-only geometry fixture exported from the game's terrain generator."""
import json
from pathlib import Path

FIXTURE = Path(__file__).resolve().parents[1]/'scenarios/people_network/terrain.json'


def load_terrain():
    return json.loads(FIXTURE.read_text())

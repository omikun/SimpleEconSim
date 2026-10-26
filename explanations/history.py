"""Small reviewed source library. Retrieval is local and never invokes web search."""
import json
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / 'data' / 'historical_parallels.json'
VERSION = '2026-10-26.1'


def candidates(packet):
    entries = json.loads(PATH.read_text())
    dimensions = ' '.join(str(value) for value in packet['selection']['subject'].values())
    text = (packet['selection']['metric_id'] + ' ' + dimensions + ' ' + ' '.join(
        e['kind'] or '' for e in packet['evidence'])).lower()
    nation = (packet.get('nation') or '').lower()
    scored = []
    for entry in entries:
        score = sum(1 for tag in entry['tags'] if tag in text)
        if not score:
            continue
        same = nation in [n.lower() for n in entry['nations']]
        # Geographic preference is a tie-breaker, not a substitute for mechanism fit.
        entry['same_nation'] = same
        entry['later_than_scenario'] = bool(packet.get('era') and entry['start_year'] > packet['era'])
        scored.append((score, int(same), entry))
    return [item[2] for item in sorted(scored, key=lambda x: (-x[0], -x[1], x[2]['id']))[:3]]

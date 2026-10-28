"""Stable synchronous first-order pressure dynamics and exact local attribution."""
import math
from .graph import Graph
from .model import CHANNELS


def advance(state, sources):
    graph, rules = Graph(state), state['rules']
    h, result, parts = rules['step'], {}, {}
    for pid, person in sorted(graph.nodes.items()):
        conductances = {}
        for eid in graph.incoming[pid]:
            edge = graph.edges[eid]
            for channel in CHANNELS:
                context = 'governing' if channel in ('player', 'rival') else 'organizing'
                conductances[eid, channel] = (edge['trust'][context] * edge['capacity']
                                               * edge['available'] * person.get('active',True)
                                               * graph.nodes[edge['source']].get('active',True))
        denom = max(1.0, math.fsum(conductances.values()) / rules['receiving_budget'])
        result[pid], parts[pid] = {}, {}
        for channel in CHANNELS:
            old = person['pressure'][channel]
            weights = [(eid, c / denom) for (eid, k), c in conductances.items() if k == channel]
            if h * (math.fsum(w for _, w in weights) + rules['anchor'] + rules['decay'] + rules.get('competition', 0.)) > 1 + 1e-12:
                raise ValueError('Unstable pressure step')
            incoming = {eid: h * w * (graph.nodes[graph.edges[eid]['source']]['pressure'][channel] - old)
                        for eid, w in weights}
            edge_total = math.fsum(incoming.values())
            source = h * sources.get(pid, {}).get(channel, 0.0)
            anchor = h * rules['anchor'] * (person['alignment'][channel] - old)
            decay = -h * rules['decay'] * old
            other = 'rival' if channel == 'player' else 'player'
            opposition = -h * rules.get('competition', 0.) * old * person['pressure'][other] if channel in ('player', 'rival') else 0.
            raw = old + edge_total + source + anchor + decay + opposition
            new = max(0.0, min(1.0, raw))
            result[pid][channel] = new
            parts[pid][channel] = dict(before=old, after=new, incoming=edge_total,
                                       source=source, anchor=anchor, decay=decay, opposition=opposition,
                                       clamp=new-raw, edges=incoming)
    return result, parts


def summary(parts):
    """Top contributors plus exact remainder; full detail is reconstructible."""
    result = {}
    for channel, p in parts.items():
        top = sorted(p['edges'].items(), key=lambda e: (-abs(e[1]), e[0]))[:3]
        result[channel] = {k: v for k, v in p.items() if k != 'edges'}
        result[channel].update(top_edges=dict(top), remainder=p['incoming']-math.fsum(v for _, v in top))
    return result


def contested(person, rules):
    a, b = person['pressure']['player'], person['pressure']['rival']
    return min(a, b) >= rules['contested_floor'] and abs(a-b) <= rules['contested_band']

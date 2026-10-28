"""One directed sparse graph. All indexes reference the same edge records."""
from collections import deque


class Graph:
    def __init__(self, state):
        self.nodes = state['people']
        self.edges = state['edges']
        self.incoming = {p: [] for p in self.nodes}
        self.outgoing = {p: [] for p in self.nodes}
        for eid, e in sorted(self.edges.items()):
            self.incoming[e['target']].append(eid)
            self.outgoing[e['source']].append(eid)

    def contacts(self, person):
        return sorted({self.edges[e]['target'] for e in self.outgoing[person]
                       if self.edges[e]['available'] and self.nodes[person].get('active',True)
                       and self.nodes[self.edges[e]['target']].get('active',True)})

    def path(self, source, target):
        todo = deque([(source, [source])])
        seen = {source}
        while todo:
            node, path = todo.popleft()
            if node == target:
                return path
            for peer in self.contacts(node):
                if peer not in seen:
                    seen.add(peer)
                    todo.append((peer, path + [peer]))
        return []

    def components(self):
        """Weak components; directed reachability is separately exposed by path()."""
        unseen, result = set(self.nodes), []
        while unseen:
            todo, group = [min(unseen)], set()
            while todo:
                node = todo.pop()
                if node in group:
                    continue
                group.add(node)
                unseen.discard(node)
                for eid in self.incoming[node] + self.outgoing[node]:
                    e = self.edges[eid]
                    if e['available'] and self.nodes[e['source']].get('active',True) and self.nodes[e['target']].get('active',True):
                        todo.append(e['source'] if e['target'] == node else e['target'])
            result.append(sorted(group))
        return result

    def boundary_edges(self):
        return [eid for eid, e in sorted(self.edges.items()) if e['available']
                and self.nodes[e['source']].get('active',True) and self.nodes[e['target']].get('active',True)
                and self.nodes[e['source']]['allegiance']
                and self.nodes[e['target']]['allegiance']
                and self.nodes[e['source']]['allegiance'] != self.nodes[e['target']]['allegiance']]

    def cut_edges(self):
        """Weak bridges, computed on demand for the small diagnostic graph."""
        pairs = {tuple(sorted((e['source'], e['target']))) for e in self.edges.values()
                 if e['available'] and self.nodes[e['source']].get('active',True) and self.nodes[e['target']].get('active',True)}
        neighbors = {p: set() for p in self.nodes}
        for a, b in pairs:
            neighbors[a].add(b)
            neighbors[b].add(a)
        bridges = []
        for a, b in sorted(pairs):
            seen, todo = {a}, [a]
            while todo:
                p = todo.pop()
                for q in sorted(neighbors[p]):
                    if {p, q} == {a, b}:
                        continue
                    if q not in seen:
                        seen.add(q)
                        todo.append(q)
            if b not in seen:
                bridges.append((a, b))
        return bridges

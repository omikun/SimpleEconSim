"""Shared trade-network topology and connectivity passes for world builders.

Consolidates the 4-pass geographic passability, corridor scoring, degree capping,
and connected-component bridging logic shared between `sim_world.py` (hex grid)
and `sim_world_voronoi.py` (Voronoi mesh), as well as ForexDesk and initial
trader wealth setup.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable


def build_trade_network_topology(
    tiles: list[Any],
    edge_mgr: Any,
    adjacent_fn: Callable[[Any], Iterable[Any]],
    *,
    is_mountain_fn: Callable[[Any], bool],
    max_trade_partners_fn: Callable[[Any], int],
    river_bonus: float = 150.0,
    strict_degree_cap_on_bridge: bool = True,
    fallback_respects_cap: bool = True,
) -> None:
    """Execute the 4-pass trade network construction on `tiles` in-place.

    Pass 0: Ensure every mountain peak has at least 1-2 passable mountain passes.
    Pass 1: Ensure every land tile with passable candidates gets >= 1 neighbor.
    Pass 2: Greedily connect high-value corridors up to `max_trade_partners_fn`.
    Pass 3: Enforce strict degree cap post-condition.
    Pass 4: Bridge disconnected land components so 100% of land tiles are reachable.
    """
    # Pass 0: Guarantee mountain peaks have at least 1-2 passable passes
    for tile in tiles:
        if getattr(tile, 'is_ocean', False):
            continue
        if is_mountain_fn(tile):
            candidates = []
            passable_count = 0
            for other in adjacent_fn(tile):
                if not getattr(other, 'is_ocean', False):
                    edge = edge_mgr.get_edge(tile.name, other.name)
                    if edge and edge.passable:
                        passable_count += 1
                    if edge:
                        candidates.append((edge.elevation_delta, other.name))
            if passable_count == 0 and candidates:
                candidates.sort(key=lambda x: x[0])
                for _, other_name in candidates[:min(2, len(candidates))]:
                    edge_mgr.unblock_mountain_pass(tile.name, other_name)

    # Gather all candidate passable land-to-land undirected edges
    candidate_edges = []
    seen_cand = set()
    for tile in tiles:
        if getattr(tile, 'is_ocean', False):
            continue
        for other in adjacent_fn(tile):
            if getattr(other, 'is_ocean', False):
                continue
            edge_key = tuple(sorted((tile.name, other.name)))
            if edge_key in seen_cand:
                continue
            if edge_mgr.is_passable(tile.name, other.name):
                seen_cand.add(edge_key)
                edge = edge_mgr.get_edge(tile.name, other.name)
                score = 100.0
                if edge and edge.is_river:
                    score += river_bonus
                if edge and edge.has_mountain_pass:
                    score += 80.0
                tile_nation = getattr(tile, 'owner_nation', None)
                other_nation = getattr(other, 'owner_nation', None)
                if tile_nation is not None and tile_nation == other_nation:
                    score += 40.0
                frict = edge.friction if edge else 1.0
                dh = abs(tile.elevation - other.elevation)
                score -= frict * 15.0 + dh * 30.0
                candidate_edges.append((score, tile, other))

    candidate_edges.sort(key=lambda x: x[0], reverse=True)

    # Pass 1: Ensure every land tile with available passable candidates gets >= 1 connection
    tile_cand_map: dict[str, list[tuple[float, Any]]] = {}
    for score, t_a, t_b in candidate_edges:
        tile_cand_map.setdefault(t_a.name, []).append((score, t_b))
        tile_cand_map.setdefault(t_b.name, []).append((score, t_a))

    for t in tiles:
        if getattr(t, 'is_ocean', False):
            continue
        if len(t.neighbors) == 0 and t.name in tile_cand_map:
            for _, cand in tile_cand_map[t.name]:
                if len(cand.neighbors) < max_trade_partners_fn(cand):
                    t.add_neighbor(cand)
                    cand.add_neighbor(t)
                    break
            if len(t.neighbors) == 0 and tile_cand_map[t.name]:
                if fallback_respects_cap:
                    sorted_cands = sorted(
                        tile_cand_map[t.name],
                        key=lambda sc: (
                            1 if (max_trade_partners_fn(sc[1]) == 2 and len(sc[1].neighbors) >= 2) else 0,
                            len(sc[1].neighbors),
                            -sc[0],
                        ),
                    )
                    best_cand = sorted_cands[0][1]
                    if len(best_cand.neighbors) < max_trade_partners_fn(best_cand):
                        t.add_neighbor(best_cand)
                        best_cand.add_neighbor(t)
                else:
                    sorted_cands = sorted(tile_cand_map[t.name], key=lambda sc: len(sc[1].neighbors))
                    best_cand = sorted_cands[0][1]
                    t.add_neighbor(best_cand)
                    best_cand.add_neighbor(t)

    # Pass 2: Greedily connect high-value corridors up to degree caps
    for _, t_a, t_b in candidate_edges:
        cap_a = max_trade_partners_fn(t_a)
        cap_b = max_trade_partners_fn(t_b)
        if len(t_a.neighbors) < cap_a and len(t_b.neighbors) < cap_b:
            if t_b.name not in t_a.neighbors:
                t_a.add_neighbor(t_b)
                t_b.add_neighbor(t_a)

    # Pass 3: Strict degree cap post-condition guarantee
    for t in tiles:
        if getattr(t, 'is_ocean', False):
            continue
        max_cap = max_trade_partners_fn(t)
        while len(t.neighbors) > max_cap:
            removable = [n for n in t.neighbors.values() if len(n.neighbors) > 1]
            if not removable:
                removable = list(t.neighbors.values())
            victim = max(
                removable,
                key=lambda n: abs(t.elevation - n.elevation) + edge_mgr.get_friction(t.name, n.name),
            )
            t.neighbors.pop(victim.name, None)
            t.routes.pop(victim.name, None)
            victim.neighbors.pop(t.name, None)
            victim.routes.pop(t.name, None)

    # Pass 4: Global Connectivity Bridging (Ensure 100% of land tiles are connected)
    land_tiles = [t for t in tiles if not getattr(t, 'is_ocean', False)]

    def _get_trade_components() -> list[list[Any]]:
        visited = set()
        comps = []
        for lt in land_tiles:
            if lt.name not in visited:
                comp = []
                queue = [lt]
                visited.add(lt.name)
                while queue:
                    curr = queue.pop(0)
                    comp.append(curr)
                    for n in curr.neighbors.values():
                        if n.name not in visited and not getattr(n, 'is_ocean', False):
                            visited.add(n.name)
                            queue.append(n)
                comps.append(comp)
        return comps

    def _can_prune_internal_edge(u: Any, v: Any, comp_nodes: list[Any]) -> bool:
        comp_set = {cn.name for cn in comp_nodes}
        visited = {u.name}
        queue = [n for n in u.neighbors.values() if n is not v and n.name in comp_set]
        visited.update(n.name for n in queue)
        while queue:
            curr = queue.pop(0)
            if curr is v:
                return True
            for n in curr.neighbors.values():
                if n.name in comp_set and n.name not in visited:
                    visited.add(n.name)
                    queue.append(n)
        return False

    trade_comps = _get_trade_components()
    while len(trade_comps) > 1:
        trade_comps.sort(key=len, reverse=True)
        main_comp = trade_comps[0]
        main_names = {t.name for t in main_comp}

        if strict_degree_cap_on_bridge:
            candidates = []
            for other_comp in trade_comps[1:]:
                for t in other_comp:
                    for other in adjacent_fn(t):
                        if other.name in main_names:
                            cap_t = max_trade_partners_fn(t)
                            cap_o = max_trade_partners_fn(other)
                            room_t = len(t.neighbors) < cap_t
                            room_o = len(other.neighbors) < cap_o

                            prune_t = None
                            if not room_t:
                                for n in list(t.neighbors.values()):
                                    if n.name not in main_names and _can_prune_internal_edge(t, n, other_comp):
                                        prune_t = n
                                        break

                            prune_o = None
                            if not room_o:
                                for n in list(other.neighbors.values()):
                                    if n.name in main_names and _can_prune_internal_edge(other, n, main_comp):
                                        prune_o = n
                                        break

                            feasible = (room_t or prune_t is not None) and (room_o or prune_o is not None)
                            dh = abs(t.elevation - other.elevation)
                            score = (
                                (1000.0 if feasible else 0.0)
                                + (100.0 if (room_t and room_o) else 0.0)
                                - dh * 20.0
                            )
                            candidates.append((score, t, other, prune_t, prune_o))

            candidates.sort(key=lambda x: x[0], reverse=True)
            if candidates:
                _, u, v, prune_u, prune_v = candidates[0]
                if prune_u:
                    u.neighbors.pop(prune_u.name, None)
                    u.routes.pop(prune_u.name, None)
                    prune_u.neighbors.pop(u.name, None)
                    prune_u.routes.pop(u.name, None)
                if prune_v:
                    v.neighbors.pop(prune_v.name, None)
                    v.routes.pop(prune_v.name, None)
                    prune_v.neighbors.pop(v.name, None)
                    prune_v.routes.pop(v.name, None)

                edge_mgr.unblock_mountain_pass(u.name, v.name)
                u.add_neighbor(v)
                v.add_neighbor(u)
                trade_comps = _get_trade_components()
            else:
                break
        else:
            best_bridge = None
            best_bridge_score = -1e9
            for other_comp in trade_comps[1:]:
                for t_other in other_comp:
                    for t_main in adjacent_fn(t_other):
                        if t_main.name in main_names and not getattr(t_main, 'is_ocean', False):
                            dh = abs(t_other.elevation - t_main.elevation)
                            score = -dh * 20.0
                            if score > best_bridge_score:
                                best_bridge_score = score
                                best_bridge = (t_other, t_main)

            if best_bridge:
                u, v = best_bridge
                edge_mgr.unblock_mountain_pass(u.name, v.name)
                u.add_neighbor(v)
                v.add_neighbor(u)
                trade_comps = _get_trade_components()
            else:
                break


def connect_claimed_forex_and_trader_wealth(tiles: list[Any], fx_module: Any, trader_wealth_fn: Callable[[Any], float]) -> None:
    """Connect ForexDesks between adjacent claimed tiles and initialize `_init_trader_wealth`."""
    seen = set()
    for a in tiles:
        if getattr(a, 'owner_nation', None) is None:
            continue
        for other in a.neighbors.values():
            if getattr(other, 'owner_nation', None) is None:
                continue
            key = tuple(sorted((a.name, other.name)))
            if key in seen:
                continue
            seen.add(key)
            fx_module.connect_desks(a, other, t=0)

    for r in tiles:
        if getattr(r, 'owner_nation', None) is not None:
            r._init_trader_wealth = trader_wealth_fn(r)
        else:
            r._init_trader_wealth = 0.0

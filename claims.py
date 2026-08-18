"""
claims.py — frontier claim mechanics for v3_wilderness (REGNUM).

Each turn, each unclaimed wilderness tile checks whether homesteaders
have established a majority originating from a specific nation.

Rules (locked in with user):
  - Total population = homesteaders + wilderness_pop (natives count as non-voting denominator).
  - A nation X claims the tile ONLY if count(origin_nation == X) / pop > 0.50 (strictly greater than 50%).
  - On claim:
      - tile.wilderness = False, tile.wilderness_pop = 0
      - Option A (v3.1) JOIN-AT-CLAIM:
          - If an adjacent claimed tile of nation X belongs to a province with
            room (< 5 tiles), the new tile JOINS that province — adopting its
            SHARED bank/government/charity.  The host is the SMALLEST such
            province (ties -> first found), so provinces grow 2->3->4->5 then
            spill into a new province; few 1- or 5-tile provinces appear.
          - If no host exists (isolated claim / all adjacent provinces full),
            a fresh 0-CAPITAL province is founded wrapping the tile.  The
            founding charter pools 5% of settler cash (cap $10) into the
            bank's share capital — a pure transfer, so NO new currency is
            ever minted by a claim.
      - Resident / Homesteader conversion (both paths):
          - All residents lose homesteader status (is_homesteader=False, homestead_since=None)
          - De-cash any wallet balance in X.currency -> hand cash
          - Repoint home_currency = X.currency, _bank_ref = province bank, region = tile.name
          - Register citizens with the province government
      - Connect ForexDesks with all adjacent claimed tiles.
      - Log event to nation.claim_log and return claim event list.

Conservation:
  - Host adoption: the tile's wilderness bundle held NO countable money; the
    shared host bank/gov/charity are already counted once by the per-currency
    audit (id-seen dedupe), so joining adds nothing to the money supply.
  - Fresh foundation: Province(zero_capital=True) creates a government with 0
    cash, a bank whose capital is zeroed, and a charity with 0 cash — exactly
    like the legacy per-tile founding path.
"""

from collections import Counter
import forex as fx
import government as govmod  # kept imported for backwards compat (probes)
import econsim_trade_money as _tm  # kept imported for backwards compat (probes)
from charity import Charity  # kept imported for backwards compat (probes)
from province import Province

MAX_PROVINCE_TILES = 5


def _find_host_province(tile, target_nation):
    """Return the best host province for *tile* (Option A join-at-claim).

    A host is an adjacent claimed tile of *target_nation* whose province has
    room (``len(prov.tiles) < MAX_PROVINCE_TILES``).  The SMALLEST such
    province is chosen (ties -> first found), so provinces fill 2->3->4->5
    before a fresh province is founded.

    Returns None when no host exists — the caller then founds a fresh
    0-capital province (isolated claim / all adjacent provinces full).
    """
    candidates = []
    for other in tile.neighbors.values():
        if getattr(other, 'wilderness', False):
            continue
        if getattr(other, 'owner_nation', None) is not target_nation:
            continue
        prov = getattr(other, 'province', None)
        if prov is not None and len(prov.tiles) < MAX_PROVINCE_TILES:
            candidates.append(prov)
    if not candidates:
        return None
    return min(candidates, key=lambda p: (len(p.tiles), id(p)))


def check_and_apply_claims(t, tiles, nations):
    """Evaluate and execute claims on all unclaimed wilderness tiles.

    Returns a list of claim event dictionaries.
    """
    claim_events = []
    nation_map = {n.name: n for n in nations}

    for tile in tiles:
        if not getattr(tile, 'wilderness', False):
            continue

        homesteaders = [a for a in tile.agents if getattr(a, 'is_homesteader', False) and getattr(a, 'alive', True)]
        homesteader_count = len(homesteaders)
        wilderness_pop = getattr(tile, 'wilderness_pop', 0)
        total_pop = homesteader_count + wilderness_pop

        if total_pop <= 0:
            continue

        # Count origin nations among homesteaders
        counts = Counter(getattr(a, 'origin_nation', None) for a in homesteaders)
        counts.pop(None, None)
        if not counts:
            continue

        best_nation_name, best_count = counts.most_common(1)[0]
        # Strictly greater than 50% pop rule
        if best_count / float(total_pop) > 0.50:
            target_nation = nation_map.get(best_nation_name)
            if target_nation is None:
                continue

            # Execute claim
            tile.wilderness = False
            tile.wilderness_pop = 0

            # ---- Option A: join an adjacent province with room, else found
            #      a fresh 0-capital province.  Both paths reuse ONE shared
            #      bundle and create NO new currency. ----
            host = _find_host_province(tile, target_nation)
            if host is not None:
                prov = host
                fresh = False
                tile._seat_gov_agent = False
            else:
                prov = Province(
                    f"{target_nation.name}-{len(target_nation.provinces)+1}",
                    target_nation, t=t, zero_capital=True)
                fresh = True
                tile._seat_gov_agent = True

            # 1. Adopt the province's shared bundle (host or fresh).
            #    `add_tile` repoints tile._institutions at prov.institutions
            #    and sets tile.province.  The tile's OLD wilderness bundle
            #    held no countable money, so nothing is abandoned / leaked.
            prov.add_tile(tile)
            tile._build_identity_factions()

            if fresh:
                # 1b. Seat the shared government agent on this sole tile
                # exactly like region._create_agents does for normal tiles and
                # the legacy claim flow did.  The per-currency audit sums
                # ``sum(a.cash for a in r.agents)`` over home-currency tiles —
                # without this append every dollar the new government collects
                # would leave the audit and read as destroyed currency.
                tile.gov.agent.region = tile.name
                tile.gov.agent._bank_ref = prov.bank
                tile.gov.agent.home_currency = target_nation.currency
                tile.agents.append(tile.gov.agent)
                # Register the new province's ownership on the nation.
                target_nation.provinces.append(prov)

            # 2. Sovereignty & Reparenting
            target_nation.add_tile(tile)

            # 3. Resident conversion
            for a in list(tile.agents):
                if a is getattr(tile, 'gov', None).agent \
                        or a is getattr(tile, 'charity', None).agent:
                    continue
                a.is_homesteader = False
                a.homestead_since = None
                a.region = tile.name
                a._bank_ref = prov.bank
                a.home_currency = target_nation.currency
                # De-cash holdings of this nation's currency from wallet to hand cash
                fx.decash_wallet(a, target_nation.currency)
                prov.gov._add_citizen(a)

            # 3b. Frontier bank founding charter (conserved): the settlers pool
            # a small share of their newly de-cashed wealth into the bank's
            # share capital.  A zero-capital bank has no loss-absorption
            # buffer: the first heirless bad-debt forgiveness would have
            # nothing to write down (capital=0, deposits=0, gov cash=0 -> the
            # M2 seniority order bottoms out and the sim raises BANK
            # INSOLVENCY).  This is a pure transfer — agent hand cash falls,
            # bank.capital (counted in bank.equity) rises — so the per-currency
            # audit sees no change.  The shared province bank absorbs the
            # charter on BOTH paths.
            for a in list(tile.agents):
                if a is getattr(tile, 'gov', None).agent \
                        or a is getattr(tile, 'charity', None).agent:
                    continue
                sub = min(max(0.0, a.cash), 10.0) * 0.05   # 5% of cash, cap $10
                if sub > 0.0:
                    a.cash -= sub
                    prov.bank.capital += sub

            # 4. Connect ForexDesks with claimed neighbors
            for other in tile.neighbors.values():
                if not getattr(other, 'wilderness', False) and getattr(other, 'owner_nation', None) is not None:
                    if tile.forex_desks.get(other.name) is None:
                        fx.connect_desks(tile, other, t=t)

            # 5. Logging
            event = {
                't': t,
                'tile': tile.name,
                'nation': target_nation.name,
                'currency': target_nation.currency,
                'homesteaders': homesteader_count,
                'pop': total_pop,
                'origin_count': best_count,
                'share': best_count / float(total_pop),
                'province': prov.name,
                'joined': not fresh,
            }
            target_nation.claim_log.append(event)
            claim_events.append(event)

    return claim_events
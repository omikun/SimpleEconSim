"""
claims.py — frontier claim mechanics for v3_wilderness (REGNUM).

Each turn, each unclaimed wilderness tile checks whether homesteaders
have established a majority originating from a specific nation.

Rules (locked in with user):
  - Total population = homesteaders + wilderness_pop (natives count as non-voting denominator).
  - A nation X claims the tile ONLY if count(origin_nation == X) / pop > 0.50 (strictly greater than 50%).
  - On claim:
      - tile.wilderness = False, tile.wilderness_pop = 0
      - Institutions initialized:
          - Government: tile.gov = Government(tile.name, t, initial_cash=0.0); tile.gov.agent.is_government = True
          - Bank: tile.bank = Bank(gov=tile.gov); tile.bank.capital = 0.0 (no free currency minting)
          - Charity: tile.charity = Charity(tile.name, tile.recipes)
          - Factions: tile._build_identity_factions()
      - Nation X takes sovereignty: X.add_tile(tile), tile.home_currency = X.currency
      - Resident / Homesteader conversion:
          - All residents lose homesteader status (is_homesteader=False, homestead_since=None)
          - De-cash any wallet balance in X.currency -> hand cash
          - Repoint home_currency = X.currency, _bank_ref = tile.bank, region = tile.name
          - Register citizens with tile.gov
      - Connect ForexDesks with all adjacent claimed tiles.
      - Log event to nation.claim_log and return claim event list.
"""

from collections import Counter
import forex as fx
import government as govmod
import econsim_trade_money as _tm
from charity import Charity


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

            # 1. Institutions
            tile.gov = govmod.Government(tile.name, t, initial_cash=0.0)
            tile.gov.agent.is_government = True
            tile.bank = _tm.Bank(gov=tile.gov)
            # Newly founded bank starts with 0.0 capital (conserved — no phantom currency minted)
            tile.bank.capital = 0.0
            tile.charity = Charity(tile.name, tile.recipes)
            tile._build_identity_factions()

            # 1b. Wire the new government agent into the tile's living-agents
            # list exactly like region._create_agents does for normal tiles.
            # The per-currency audit (forex.audit_currency_total) sums
            # ``sum(a.cash for a in r.agents)`` — WITHOUT this append, every
            # dollar the new government collects (taxes, heirless probate,
            # import escheat) leaves the audit and reads as destroyed currency
            # on the freshly-claimed tile.
            tile.gov.agent.region = tile.name
            tile.gov.agent._bank_ref = tile.bank
            tile.gov.agent.home_currency = target_nation.currency
            tile.agents.append(tile.gov.agent)

            # 2. Sovereignty & Reparenting
            target_nation.add_tile(tile)

            # 3. Resident conversion
            for a in list(tile.agents):
                if a is tile.gov.agent or a is getattr(tile.charity, 'agent', None):
                    continue
                a.is_homesteader = False
                a.homestead_since = None
                a.region = tile.name
                a._bank_ref = tile.bank
                a.home_currency = target_nation.currency
                # De-cash holdings of this nation's currency from wallet to hand cash
                fx.decash_wallet(a, target_nation.currency)
                tile.gov._add_citizen(a)

            # 3b. Frontier bank founding charter (conserved): the settlers pool
            # a small share of their newly de-cashed wealth into the bank's
            # share capital.  A zero-capital bank has no loss-absorption
            # buffer: the first heirless bad-debt forgiveness would have
            # nothing to write down (capital=0, deposits=0, gov cash=0 -> the
            # M2 seniority order bottoms out and the sim raises BANK
            # INSOLVENCY).  This is a pure transfer — agent hand cash falls,
            # bank.capital (counted in bank.equity) rises — so the per-currency
            # audit sees no change.
            for a in list(tile.agents):
                if a is tile.gov.agent or a is getattr(tile.charity, 'agent', None):
                    continue
                sub = min(max(0.0, a.cash), 10.0) * 0.05   # 5% of cash, cap $10
                if sub > 0.0:
                    a.cash -= sub
                    tile.bank.capital += sub

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
            }
            target_nation.claim_log.append(event)
            claim_events.append(event)

    return claim_events

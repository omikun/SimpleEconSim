"""
v3_wilderness — unclaimed-tile mechanics for the REGNUM tile game.

Every behavior that only applies to UNCLAIMED (wilderness) tiles lives here,
keeping region.py lean.  Functions take a Region instance (duck-typed), so
this module never imports region.py — no import cycle.

Rulings locked with the user (2026-08-13/14):
  - Homesteaders forage ``+1 food`` every ``FORAGE_INTERVAL`` turns, and ONLY
    while they live on an unclaimed tile.  Foraging never happens on claimed
    tiles.
  - A homesteader who lands on a claimed tile immediately LOSES homesteader
    status (``is_homesteader`` cleared, ``homestead_since`` reset).
  - Unclaimed tiles are currency-less (``home_currency=None``), with no bank,
    government, charity, or factions.  ``wilderness_pop`` is a non-ticking
    scalar (0-50) used only as a pop-count denominator for the claim rule.
  - Homesteaders carry their money in FX wallets: hand cash is walletized on
    entering an unclaimed tile and de-cashed when the tile is claimed or the
    agent settles on a claimed tile of that same currency.  Foreign balances
    stay in the wallet (no FX conversion ever).
"""

import forex as fx
from goods import Goods


# Homesteaders on an UNCLAIMED tile forage +1 food every this many turns.
FORAGE_INTERVAL = 3


# =============================================================================
# Agent transitions (conservation-safe, wallet portability)
# =============================================================================

def enter_wilderness(region, agent, t):
    """Land *agent* on an unclaimed tile (homesteader status begins)."""
    if getattr(region, 'is_ocean', False) or getattr(region, 'elevation', 0.0) < 0.0:
        return 0.0
    moved = 0.0
    if agent.cash > 0 and agent.home_currency:
        moved = fx.walletize(agent, agent.home_currency)
    agent.is_homesteader = True
    agent.homestead_since = t
    agent.last_forage_turn = t
    agent.home_currency = None
    agent._bank_ref = None
    agent.region = region.name
    if agent not in region.agents:
        region.agents.append(agent)
    return moved


def enter_claimed(region, agent, t):
    """Land *agent* on a claimed tile — homesteading ENDS.

    - any hand cash (e.g. an origin-currency deposit withdrawn for a move)
      is walletized into the agent's CURRENT home currency FIRST, so money
      stays countable by ``audit_currency_total`` (which sums every agent's
      FX wallets regardless of residence) even when the agent's residence
      tile changes ownership currency — without this, origin-currency cash
      would sit "stranded" on a foreign tile and vanish from the audit,
    - ``is_homesteader=False``, ``homestead_since=None``,
    - any wallet balance in the tile's currency moves back to hand cash
      (a same-nation homesteader de-cashes fully; a foreign homesteader's
      foreign balances stay in the wallet),
    - ``home_currency`` and ``_bank_ref`` repointed to the tile's.

    Caller must remove *agent* from its previous region's ``agents`` list.
    """
    # Preserve origin-currency holdings before the residence currency changes.
    if agent.cash > 0 and agent.home_currency:
        fx.walletize(agent, agent.home_currency)
    agent.is_homesteader = False
    agent.homestead_since = None
    if region.home_currency:
        fx.decash_wallet(agent, region.home_currency)
        agent.home_currency = region.home_currency
    agent._bank_ref = region.bank
    agent.region = region.name
    if agent not in region.agents:
        region.agents.append(agent)


# =============================================================================
# Foraging (the ONLY goods creation on unclaimed land)
# =============================================================================

import foraging as _foraging


def forage(region, t):
    """Homesteaders on an unclaimed tile forage (+1 food) on schedule."""
    return _foraging.forage_tile(region, t)


# =============================================================================
# Per-turn wilderness step
# =============================================================================

_GOODS_TRADE = (Goods.food, Goods.wood, Goods.furniture, Goods.transport)


def _align_logs(region):
    """Append one entry to every metric series the viewer/audit reads.

    Wilderness tiles never run the market lifecycle, so these series would
    stay empty and crash ``[-1]`` readers.  Pure bookkeeping — no money or
    goods move here.
    """
    for g in region.goods:
        if g == Goods.gov:
            continue
        region.production_log[g].append(0)
        region.population_log[g].append(0)
        region.hungry_log[g].append(0)
        region.inventory_log[g].append(0.0)
        region.per_capita_inventory[g].append(0.0)
        region.cash_log[g].append(0.0)
        region.gini_log[g].append(0.0)
        region.demand_ratio_log[g].append(0.0)
        region.demand_log[g].append(0)
        region.supply_log[g].append(0)
        region.sold_log[g].append(0)
        region.price_log[g].append(region.recipes[g]['price'])
        region.gdp_by_profession_log[g].append(0)
    for key in ('trader',):
        region.population_log[key].append(0)
        region.cash_log[key].append(0.0)
        region.gini_log[key].append(0.0)
        region.hungry_log[key].append(0)
        region.inventory_log[key].append(0.0)
        region.per_capita_inventory[key].append(0.0)
        region.production_log[key].append(0)
        region.gdp_by_profession_log[key].append(0)
    for g in _GOODS_TRADE:
        region.export_vol[g].append(0)
        region.export_val[g].append(0.0)
        region.import_vol[g].append(0)
        region.import_val[g].append(0.0)
        region.price_spread_log[g].append(0.0)


def step_wilderness(region, t):
    """One turn of an unclaimed wilderness tile (v3).

    Forages scheduled homesteaders, then aligns every metric series so
    downstream readers (viewer, sim drivers, audits) see consistent-length
    logs.  No conservation impact except the sanctioned foraged food.
    """
    foraged = forage(region, t)
    _align_logs(region)
    # This turn's food-production entry reflects the foraged units (GDP too).
    region.production_log[Goods.food][-1] = foraged
    region.population_log[Goods.food][-1] = len(region.agents)
    food_val = foraged * region.recipes[Goods.food]['price']
    region.gdp_by_profession_log[Goods.food][-1] = food_val
    region.gdp_log.append(food_val)
    region.total_population.append(len(region.agents))
    region.cost_of_living_log.append(region.cost_of_living)
    region.migration_intent_log.append(0.0)
    region.faction_support_log.append({})
    region.faction_grievance_log.append({})
    region.protest_energy_log.append(0.0)
    region.unrest_log.append({'stage': 'calm', 'looted': 0.0, 't': t})
    region.total_cash_log.append(0.0)
    region.bank_cash_log.append(0.0)
    region.trader_cash_log.append(0.0)
    region.pipeline_depth_log.append(0)
    region.population_change_rate_log.append(0.0)
    region.forage_log.append((t, foraged, len(region.agents)))
    region.tenure_log.append(1.0)
    region.social_class_log.append({'serf': len(region.agents)})
    region.food_foraged_log.append(foraged)
    region.food_purchased_log.append(0)
    region.rent_collected_log.append(0.0)
    region.rent_arrears_log.append(0.0)
    region.avg_shift_hours_log.append(8.0)
    region.surplus_value_log.append(0.0)
    region.rate_of_exploitation_log.append(0.0)
    region.avg_alienation_log.append(0.0)
    region.avg_health_attrition_log.append(0.0)
    region.avg_consciousness_log.append(0.0)
    region.workplace_accidents_log.append(0)
    region.entertainment_log.append(0.0)
    region.strikers_log.append(0)
    region.broken_machinery_log.append(0)
    region.sabotage_log.append(0)
    if hasattr(region, 'tribute_collected_log'):
        region.tribute_collected_log.append(0.0)
    if hasattr(region, 'tax_distribution_log'):
        region.tax_distribution_log.append({'total': 0.0, 'municipal': 0.0, 'provincial': 0.0, 'national': 0.0})
    if hasattr(region, 'grievance_sources_log'):
        region.grievance_sources_log.append({
            'raw': {'overworked': 0.0, 'rent_enclosure': 0.0, 'hunger': 0.0, 'labor_resistance': 0.0, 'unemployment': 0.0, 'tax': 0.0, 'repression': 0.0, 'inequality': 0.0},
            'pct': {'overworked': 0.0, 'rent_enclosure': 0.0, 'hunger': 0.0, 'labor_resistance': 0.0, 'unemployment': 0.0, 'tax': 0.0, 'repression': 0.0, 'inequality': 0.0},
            'total': 0.0,
            'protest': 0.0,
        })
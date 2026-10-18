"""
ai_nation.py — AI Sovereign Brain, Terrain Valuation, Vulnerability, and Alliances for Call of Capital (M5).

Provides:
- NationPolicyAI: strategic brain for an AI-controlled Nation.
- M5.1 Terrain Valuation & Bottleneck Relief: scores adjacent/candidate tiles based on
  production capacity, recipe modifiers, and national shortage relief (demand_ratio / price_spread).
- M5.2 Vulnerability & Fortification: calculates border vulnerability against hostile neighbors;
  reinforces weak points or seeks diplomatic non-aggression treaties.
- M5.3 Expansion Drive: evaluates expansion vectors (settle vs annex vs conquest) with player-visible reason strings.
- M5.4–M5.7 Diplomacy & Alliances: forms counterbalancing defensive alliances against aggressive powers,
  aligns into ideological blocs, and re-evaluates/betrays partners when threat matrices shift.
"""

from __future__ import annotations
import random
from goods import Goods
from diplomacy import DiplomacySystem, TreatyType, get_diplomacy
from army import MilitaryUnit, recruit_unit
from intents import (RecruitArmyIntent, MoveArmyIntent, ProposeTreatyIntent,
                     BreakTreatyIntent, DeclareWarIntent, BuildIntent,
                     SubsidizeContractorIntent, ProposePeaceIntent,
                     RespondPeaceIntent)
from war_logic import (aim_secured, attack_forecasts, effective_strength,
                       supply_runway)


def _war_ai_trace_context(nation, enemy, war, turn, shared=None):
    if shared is not None:
        return shared
    regions = list(getattr(nation, 'tiles', ())) + list(
        getattr(enemy, 'tiles', ()))
    region = next((tile for tile in regions
                   if getattr(tile, '_run_trace', None) is not None
                   and getattr(tile, '_collective_trace_clock', None) is not None),
                  None)
    if region is None:
        return None
    clock = region._collective_trace_clock
    trace_turn = int(clock.get('turn', turn))
    return {'region': region, 'turn': trace_turn,
            'operation_id': (f'war-ai:{nation.name}:{enemy.name}:'
                             f'{int(war.declared_turn)}:{trace_turn}:'
                             f'{int(clock.get("next", 0))}'),
            'event_ids': [], 'last_event_id': None}


def _emit_war_ai_trace(context, *, kind, nation, enemy, metric_id, unit,
                       after, inputs, before=None, record_class='decision',
                       formula_id=None, cause_event_ids=None):
    if context is None:
        return None
    from run_trace import emit
    event_inputs = dict(inputs or {})
    event_inputs.setdefault('operation_id', context['operation_id'])
    event_inputs.setdefault('turn', context['turn'])
    event_id = emit(
        context['region'], kind=kind, record_class=record_class,
        phase='strategy',
        subject={'type': 'nation/opponent', 'id': nation.name,
                 'opponent': enemy.name},
        metric_id=metric_id, unit=unit, before=before, after=after,
        inputs=event_inputs, formula_id=formula_id,
        cause_event_ids=cause_event_ids)
    if event_id is not None:
        context.setdefault('event_ids', []).append(event_id)
        context['last_event_id'] = event_id
    return event_id


class NationPolicyAI:
    """Strategic decision-making intelligence for one sovereign Nation."""

    def __init__(self, nation, personality: dict | None = None):
        self.nation = nation
        # Personality traits (0.0 to 1.0)
        self.personality = personality or {
            'expansionist': 0.6,
            'militarism': 0.5,
            'diplomatic': 0.7,
            'risk_tolerance': 0.4,
            'loyalty': 0.8
        }
        self.decision_log: list[dict] = []

    # ------------------------------------------------------------------
    # M5.1 Terrain Valuation & Bottleneck Relief
    # ------------------------------------------------------------------

    def score_terrain_value(self, tile) -> float:
        """Calculate raw economic and productive value of *tile* (M5.1).

        Reads recipe modifiers (fertility/terrain), climate, and baseline output.
        """
        return self._terrain_value_breakdown(tile)['score']

    def _terrain_value_breakdown(self, tile) -> dict:
        score = 0.0
        recipes = getattr(tile, 'recipes', {})
        good_values = []
        for g in [Goods.food, Goods.wood, Goods.furniture]:
            recipe = recipes.get(g, {})
            base_price = recipe.get('price', 10.0)
            mult = recipe.get('productivity_mult', 1.0)
            contribution = base_price * mult
            score += contribution
            good_values.append({'good': g.name, 'reference_price': base_price,
                                'productivity_multiplier': mult,
                                'score_contribution': contribution})

        # Climate adjustment
        climate = getattr(tile, 'climate', 'temperate')
        climate_multiplier = 1.0
        if climate == 'cold':
            climate_multiplier = 0.8
        elif climate == 'fertile':
            climate_multiplier = 1.4
        goods_score_before_climate = score
        score *= climate_multiplier
        climate_adjusted_goods_score = score

        # Native population base value
        pop = len(getattr(tile, 'agents', [])) + getattr(tile, 'wilderness_pop', 0)
        population_score = min(50.0, pop * 0.5)
        score += population_score
        return {'goods': good_values,
                'goods_score_before_climate': goods_score_before_climate,
                'climate': climate,
                'climate_multiplier': climate_multiplier,
                'climate_adjusted_goods_score': climate_adjusted_goods_score,
                'native_population': pop,
                'population_score_cap': 50.0,
                'population_score_per_person': 0.5,
                'population_score': population_score,
                'score': score}

    def score_bottleneck_relief(self, tile) -> float:
        """Calculate how much *tile* relieves this nation's resource bottlenecks (M5.1).

        Analyzes own tiles' demand_ratio_log and price_spread_log for shortages.
        """
        return self._bottleneck_relief_breakdown(tile)['bonus']

    def _bottleneck_relief_breakdown(self, tile) -> dict:
        bonus = 0.0
        own_tiles = self.nation.tiles

        # Check for food or wood scarcity in own nation
        avg_food_price = 0.0
        avg_wood_price = 0.0
        if own_tiles:
            avg_food_price = sum(t.recipes.get(Goods.food, {}).get('price', 10.0) for t in own_tiles) / len(own_tiles)
            avg_wood_price = sum(t.recipes.get(Goods.wood, {}).get('price', 10.0) for t in own_tiles) / len(own_tiles)

        tile_recipes = getattr(tile, 'recipes', {})
        # If own food is expensive (> $15) and candidate tile has food advantage
        food_price_gate = avg_food_price > 15.0
        food_productivity = None
        food_productivity_gate = False
        if food_price_gate:
            food_productivity = tile_recipes.get(
                Goods.food, {}).get('productivity_mult', 1.0)
            food_productivity_gate = food_productivity > 1.2
        food_bonus = ((avg_food_price - 10.0) * 3.0
                      if food_price_gate and food_productivity_gate else 0.0)
        bonus += food_bonus

        # If own wood is expensive (> $25) and candidate tile has wood advantage
        wood_price_gate = avg_wood_price > 25.0
        wood_productivity = None
        wood_productivity_gate = False
        if wood_price_gate:
            wood_productivity = tile_recipes.get(
                Goods.wood, {}).get('productivity_mult', 1.0)
            wood_productivity_gate = wood_productivity > 1.2
        wood_bonus = ((avg_wood_price - 20.0) * 2.5
                      if wood_price_gate and wood_productivity_gate else 0.0)
        bonus += wood_bonus

        return {'bonus': bonus,
                'own_average_food_price': avg_food_price,
                'own_average_wood_price': avg_wood_price,
                'food_price_threshold': 15.0,
                'food_productivity_threshold': 1.2,
                'food_bonus_price_base': 10.0,
                'food_bonus_price_multiplier': 3.0,
                'candidate_food_productivity': food_productivity,
                'food_price_gate': food_price_gate,
                'food_productivity_gate': food_productivity_gate,
                'food_bonus': food_bonus,
                'wood_price_threshold': 25.0,
                'wood_productivity_threshold': 1.2,
                'wood_bonus_price_base': 20.0,
                'wood_bonus_price_multiplier': 2.5,
                'candidate_wood_productivity': wood_productivity,
                'wood_price_gate': wood_price_gate,
                'wood_productivity_gate': wood_productivity_gate,
                'wood_bonus': wood_bonus}

    def _candidate_tile_valuation(self, tile) -> dict:
        terrain = self._terrain_value_breakdown(tile)
        bottleneck = self._bottleneck_relief_breakdown(tile)
        total = terrain['score'] + bottleneck['bonus']
        reason = (f"Terrain score: {terrain['score']:.1f}, Bottleneck relief bonus: "
                  f"{bottleneck['bonus']:.1f} (Total: {total:.1f})")
        return {'score': total, 'reason': reason,
                'terrain': terrain, 'bottleneck_relief': bottleneck}

    def evaluate_candidate_tile(self, tile) -> tuple[float, str]:
        """Total desirability score for acquiring *tile* with explanation string."""
        valuation = self._candidate_tile_valuation(tile)
        return valuation['score'], valuation['reason']

    # ------------------------------------------------------------------
    # M5.2 Vulnerability & Military Posture
    # ------------------------------------------------------------------

    def evaluate_tile_vulnerability(self, tile, all_nations: list,
                                    diplomacy: DiplomacySystem) -> tuple[float, str]:
        """Calculate threat / vulnerability score for an owned *tile* (0.0 to 1.0) (M5.2)."""
        if getattr(tile, 'owner_nation', None) is not self.nation:
            return 0.0, "Tile not owned"

        # Local friendly military strength
        local_units = [u for u in getattr(self.nation, 'military_units', []) if u.region_name == tile.name]
        local_strength = sum(u.strength for u in local_units)

        # Hostile / rival neighbor military strength adjacent to this tile
        hostile_adjacent_strength = 0.0
        threat_sources = []

        for other in tile.neighbors.values():
            other_owner = getattr(other, 'owner_nation', None)
            if other_owner is None or other_owner is self.nation:
                continue

            rel = diplomacy.get_relation(self.nation.name, other_owner.name)
            is_allied = diplomacy.has_treaty(self.nation.name, other_owner.name, TreatyType.DEFENSIVE_ALLIANCE.value)
            is_nap = diplomacy.has_treaty(self.nation.name, other_owner.name, TreatyType.NON_AGGRESSION.value)

            if is_allied or is_nap:
                continue

            # Check military units on the neighbor tile
            enemy_units = [u for u in getattr(other_owner, 'military_units', []) if u.region_name == other.name]
            enemy_strength = sum(u.strength for u in enemy_units)

            # Weight by hostility
            hostility = max(0.2, (0.2 - rel))  # higher if relation is negative
            weighted_threat = enemy_strength * hostility
            if weighted_threat > 0:
                hostile_adjacent_strength += weighted_threat
                threat_sources.append(other_owner.name)

        if hostile_adjacent_strength <= 0:
            return 0.0, "Secure border: no hostile forces detected."

        vulnerability = min(1.0, hostile_adjacent_strength / max(10.0, local_strength + 10.0))
        reason = (f"Vulnerability: {vulnerability:.2f} (Local strength: {local_strength:.1f} vs "
                  f"Threat from {', '.join(set(threat_sources))}: {hostile_adjacent_strength:.1f})")
        return vulnerability, reason

    # ------------------------------------------------------------------
    # M5.3 Expansion Drive
    # ------------------------------------------------------------------

    def evaluate_expansion(self, all_tiles: list, all_nations: list,
                           diplomacy: DiplomacySystem) -> dict | None:
        """Find the best adjacent expansion opportunity and return plan dict (M5.3)."""
        best_score = -999.0
        best_plan = None

        # Find all adjacent non-owned tiles
        candidates = set()
        candidate_gate_evaluations = []
        for own_tile in self.nation.tiles:
            for neighbor in own_tile.neighbors.values():
                owner = getattr(neighbor, 'owner_nation', None)
                ocean = None
                elevation = None
                if owner is self.nation:
                    reason = 'already_owned'
                    eligible = False
                else:
                    ocean = getattr(neighbor, 'is_ocean', False)
                    if ocean:
                        reason = 'ocean_tile'
                        eligible = False
                    else:
                        elevation = getattr(neighbor, 'elevation', 0.0)
                        eligible = elevation >= 0.0
                        reason = ('adjacent_land_candidate' if eligible else
                                  'below_sea_level')
                candidate_gate_evaluations.append({
                    'from_tile': own_tile.name,
                    'candidate_tile': neighbor.name,
                    'owner': getattr(owner, 'name', None),
                    'is_ocean': ocean,
                    'elevation': elevation,
                    'eligible': eligible,
                    'reason': reason})
                if eligible:
                    candidates.add(neighbor)

        candidate_evaluations = []
        selected_candidate_index = None
        for candidate_index, tile in enumerate(candidates):
            valuation = self._candidate_tile_valuation(tile)
            score, val_reason = valuation['score'], valuation['reason']
            owner = getattr(tile, 'owner_nation', None)
            evaluation = {
                'candidate_order_index': candidate_index,
                'tile': tile.name,
                'owner': getattr(owner, 'name', None),
                'valuation_score': score,
                'valuation_reason': val_reason,
                'valuation_components': {
                    'terrain': valuation['terrain'],
                    'bottleneck_relief': valuation['bottleneck_relief']},
                'candidate_mode_eligible': False,
                'eligible_plan': False,
                'selected': False}

            if owner is None:
                # Wilderness / unowned tile: settlement vector
                cost = 20.0
                net_score = score * self.personality['expansionist'] - cost * 0.1
                evaluation.update({
                    'mode': 'settle', 'candidate_mode_eligible': True,
                    'plan_score': net_score,
                    'score_formula': 'valuation*expansionist - 20*0.1',
                    'expansionist': self.personality['expansionist'],
                    'settlement_cost': cost,
                    'settlement_cost_weight': 0.1})
                plan = {
                    'tile': tile,
                    'mode': 'settle',
                    'score': net_score,
                    'reason': f"Expand into wilderness {tile.name} ({val_reason})"
                }
            else:
                # Owned by foreign nation: conquest vs diplomatic fallout
                rel = diplomacy.get_relation(self.nation.name, owner.name)
                is_allied = diplomacy.has_treaty(self.nation.name, owner.name, TreatyType.DEFENSIVE_ALLIANCE.value)
                fallout_penalty = (100.0 if is_allied else 30.0) * (rel + 1.0)
                
                # Check military balance
                own_military = sum(u.strength for u in getattr(self.nation, 'military_units', []))
                enemy_military = sum(u.strength for u in getattr(owner, 'military_units', []))

                if own_military > enemy_military * 1.3 and not is_allied:
                    net_score = score * self.personality['militarism'] * 1.5 - fallout_penalty
                    evaluation.update({
                        'mode': 'conquest', 'target_nation': owner.name,
                        'candidate_mode_eligible': True,
                        'relation': rel, 'defensive_alliance': is_allied,
                        'diplomatic_fallout_multiplier':
                            100.0 if is_allied else 30.0,
                        'diplomatic_fallout_penalty': fallout_penalty,
                        'own_military_strength': own_military,
                        'enemy_military_strength': enemy_military,
                        'military_advantage_multiplier': 1.3,
                        'military_advantage_gate': True,
                        'militarism': self.personality['militarism'],
                        'plan_score': net_score,
                        'score_formula':
                            'valuation*militarism*1.5 - diplomatic_fallout'})
                    plan = {
                        'tile': tile,
                        'mode': 'conquest',
                        'target_nation': owner.name,
                        'score': net_score,
                        'reason': f"Annex {tile.name} from {owner.name} by force ({val_reason})"
                    }
                else:
                    evaluation.update({
                        'mode': 'conquest', 'target_nation': owner.name,
                        'relation': rel, 'defensive_alliance': is_allied,
                        'diplomatic_fallout_multiplier':
                            100.0 if is_allied else 30.0,
                        'diplomatic_fallout_penalty': fallout_penalty,
                        'own_military_strength': own_military,
                        'enemy_military_strength': enemy_military,
                        'military_advantage_multiplier': 1.3,
                        'military_advantage_gate':
                            own_military > enemy_military * 1.3,
                        'candidate_mode_eligible': False,
                        'eligible_plan': False,
                        'reason': ('defensive_alliance_blocks_conquest'
                                   if is_allied else
                                   'insufficient_military_advantage')})
                    candidate_evaluations.append(evaluation)
                    continue

            plan_score_gate = plan['score'] > 5.0
            evaluation.update({'eligible_plan': plan_score_gate,
                               'plan_score_threshold': 5.0,
                               'plan_score_gate': plan_score_gate,
                               'selected': False})
            if plan['score'] > best_score and plan['score'] > 5.0:
                if selected_candidate_index is not None:
                    candidate_evaluations[selected_candidate_index][
                        'selected'] = False
                    candidate_evaluations[selected_candidate_index][
                        'selection_result'] = 'superseded_by_higher_score'
                best_score = plan['score']
                best_plan = plan
                evaluation['selected'] = True
                evaluation['selection_result'] = 'highest_score_so_far'
                selected_candidate_index = len(candidate_evaluations)
            elif plan['score'] <= 5.0:
                evaluation['selection_result'] = 'below_minimum_plan_score'
            elif plan['score'] == best_score:
                evaluation['selection_result'] = 'tie_kept_earlier_candidate'
            else:
                evaluation['selection_result'] = 'lower_score_than_selected_plan'
            candidate_evaluations.append(evaluation)

        selected_summary = ({'tile': best_plan['tile'].name,
                             'mode': best_plan['mode'],
                             'target_nation': best_plan.get('target_nation'),
                             'score': best_plan['score'],
                             'reason': best_plan['reason']}
                            if best_plan is not None else
                            {'tile': None, 'mode': None, 'score': None,
                             'reason': 'no_candidate_passed_plan_gates'})
        trace_region = next((tile for tile in self.nation.tiles
                             if getattr(tile, '_run_trace', None) is not None
                             and getattr(tile, '_collective_trace_clock', None)
                             is not None), None)
        if trace_region is not None:
            from run_trace import emit
            clock = trace_region._collective_trace_clock
            trace_turn = int(clock.get('turn', 0))
            operation_id = (f'expansion:{self.nation.name}:{trace_turn}:'
                            f'{int(clock.get("next", 0))}')
            emit(
                trace_region, kind='nation_expansion_evaluation',
                record_class='decision', phase='strategy',
                subject={'type': 'nation', 'id': self.nation.name},
                metric_id='expansion.ai_candidates', unit='plan',
                after=selected_summary,
                inputs={
                    'operation_id': operation_id,
                    'turn': trace_turn,
                    'all_tile_count': len(all_tiles),
                    'all_nation_count': len(all_nations),
                    'candidate_gate_count': len(candidate_gate_evaluations),
                    'candidate_gate_evaluations': candidate_gate_evaluations,
                    'candidate_count': len(candidates),
                    'candidate_evaluations': candidate_evaluations,
                    'selected_plan': selected_summary,
                    'minimum_plan_score': 5.0,
                    'candidate_iteration_order':
                        'existing_set_iteration; strict greater-than keeps first tie'}
            )

        return best_plan

    # ------------------------------------------------------------------
    # M5.4–M5.7 Diplomacy, Alliances, Blocs & Betrayals
    # ------------------------------------------------------------------

    def evaluate_diplomacy(self, all_nations: list, diplomacy: DiplomacySystem,
                           t: int = 0) -> list[object]:
        """Generate diplomatic intents (alliances, trade pacts, betrayals, wars)."""
        intents = []
        other_nations = [n for n in all_nations if n.name != self.nation.name]
        candidate_evaluations = []

        # Calculate relative military strength of all nations
        mil_strengths = {
            n.name: sum(u.strength for u in getattr(n, 'military_units', []))
            for n in all_nations
        }
        my_strength = mil_strengths.get(self.nation.name, 0.0)

        # 1. Identify dominant expansionist threat in the world (M5.5)
        threat_nation = None
        max_threat_score = 0.0
        for other in other_nations:
            other_str = mil_strengths.get(other.name, 0.0)
            rel = diplomacy.get_relation(self.nation.name, other.name)
            strength_gate = other_str > my_strength * 1.4
            relation_gate = rel < 0.2
            eligible = strength_gate and relation_gate
            selected = False
            if eligible:
                if other_str > max_threat_score:
                    max_threat_score = other_str
                    threat_nation = other
                    selected = True
            candidate_evaluations.append({
                'policy': 'dominant_threat', 'target': other.name,
                'military_strength': other_str,
                'own_military_strength': my_strength,
                'strength_threshold_multiplier': 1.4,
                'strength_gate': strength_gate,
                'relation': rel, 'relation_threshold': 0.2,
                'relation_gate': relation_gate, 'eligible': eligible,
                'selected': selected,
                'reason': ('strongest_eligible_threat' if selected else
                           'not_stronger_than_selected_threat' if eligible else
                           'military_threshold_not_met' if not strength_gate else
                           'relations_not_hostile_enough')})

        # In the (unusual) event that later eligible candidates replaced the
        # provisional strongest target, preserve exactly one selected row.
        if threat_nation is not None:
            for row in candidate_evaluations:
                if row['policy'] == 'dominant_threat':
                    row['selected'] = row['target'] == threat_nation.name
                    if row['eligible'] and not row['selected']:
                        row['reason'] = 'not_stronger_than_selected_threat'

        # 2. Counterbalancing Alliance Formation (M5.5)
        if threat_nation is not None:
            alliance_selected = False
            for ally_cand in other_nations:
                if ally_cand.name == threat_nation.name:
                    candidate_evaluations.append({
                        'policy': 'counterbalance_alliance',
                        'target': ally_cand.name, 'eligible': False,
                        'selected': False, 'reason': 'dominant_threat_excluded'})
                    continue
                # If ally candidate also faces threat from threat_nation and is not allied
                if alliance_selected:
                    candidate_evaluations.append({
                        'policy': 'counterbalance_alliance',
                        'target': ally_cand.name, 'eligible': None,
                        'selected': False,
                        'reason': 'not_evaluated_after_first_eligible_partner'})
                    continue
                has_alliance = diplomacy.has_treaty(
                    self.nation.name, ally_cand.name,
                    TreatyType.DEFENSIVE_ALLIANCE.value)
                rel = diplomacy.get_relation(self.nation.name, ally_cand.name)
                relation_gate = rel >= -0.1
                eligible = not has_alliance and relation_gate
                selected = eligible
                candidate_evaluations.append({
                    'policy': 'counterbalance_alliance',
                    'target': ally_cand.name,
                    'dominant_threat': threat_nation.name,
                    'has_defensive_alliance': has_alliance,
                    'relation': rel, 'relation_threshold': -0.1,
                    'relation_gate': relation_gate, 'eligible': eligible,
                    'selected': selected,
                    'reason': ('first_eligible_counterbalance_partner' if selected else
                               'defensive_alliance_already_active' if has_alliance else
                               'relations_too_hostile')})
                if eligible:
                    intents.append(ProposeTreatyIntent(
                        nation_name=self.nation.name,
                        target_nation_name=ally_cand.name,
                        treaty_type=TreatyType.DEFENSIVE_ALLIANCE.value,
                        submitted_turn=t,
                        regime_type=self.nation.regime_type
                    ))
                    alliance_selected = True
        else:
            candidate_evaluations.append({
                'policy': 'counterbalance_alliance', 'eligible': False,
                'selected': False, 'reason': 'no_dominant_threat'})

        # 3. Bilateral Trade Pacts (M5.4)
        for other in other_nations:
            has_pact = diplomacy.has_treaty(
                self.nation.name, other.name, TreatyType.TRADE_PACT.value)
            rel = diplomacy.get_relation(self.nation.name, other.name)
            relation_gate = rel >= 0.1
            eligible = not has_pact and relation_gate
            candidate_evaluations.append({
                'policy': 'trade_pact', 'target': other.name,
                'has_trade_pact': has_pact, 'relation': rel,
                'relation_threshold': 0.1, 'relation_gate': relation_gate,
                'eligible': eligible, 'selected': eligible,
                'reason': ('relations_meet_trade_pact_threshold' if eligible else
                           'trade_pact_already_active' if has_pact else
                           'relations_below_trade_pact_threshold')})
            if eligible:
                intents.append(ProposeTreatyIntent(
                    nation_name=self.nation.name,
                    target_nation_name=other.name,
                    treaty_type=TreatyType.TRADE_PACT.value,
                    submitted_turn=t,
                    regime_type=self.nation.regime_type
                ))

        # 4. Betrayal & Backstabbing Re-evaluation (M5.7)
        # If an ally has become very weak and possesses high-value bottleneck resources,
        # or has grown dangerously hostile despite a treaty, consider breaking treaty.
        for tr in diplomacy.get_active_treaties(self.nation.name):
            partner_name = tr.partner_of(self.nation.name)
            partner = next((n for n in all_nations if n.name == partner_name), None)
            if not partner:
                candidate_evaluations.append({
                    'policy': 'treaty_betrayal', 'target': partner_name,
                    'treaty_type': tr.treaty_type, 'eligible': False,
                    'selected': False, 'reason': 'treaty_partner_not_in_current_nation_list'})
                continue

            partner_str = mil_strengths.get(partner.name, 0.0)
            rel = diplomacy.get_relation(self.nation.name, partner.name)

            # Betrayal condition: partner is crippled (low military) while self has strong militarism
            # and low loyalty, or relations collapsed into negative
            weak_partner = partner_str < 10.0
            strong_self = my_strength > 50.0
            low_loyalty = self.personality['loyalty'] < 0.5
            weak_partner_relation_gate = rel < 0.3
            opportunistic_betrayal = (weak_partner and strong_self
                                      and low_loyalty
                                      and weak_partner_relation_gate)
            hostile_relation = rel < -0.4
            eligible = opportunistic_betrayal or hostile_relation
            candidate_evaluations.append({
                'policy': 'treaty_betrayal', 'target': partner.name,
                'treaty_type': tr.treaty_type,
                'partner_military_strength': partner_str,
                'own_military_strength': my_strength,
                'loyalty': self.personality['loyalty'],
                'relation': rel,
                'opportunistic_gates': {
                    'partner_below_10_strength': weak_partner,
                    'self_above_50_strength': strong_self,
                    'loyalty_below_0_5': low_loyalty,
                    'relation_below_0_3': weak_partner_relation_gate},
                'hostile_relation_gate': {'threshold': -0.4,
                                          'passed': hostile_relation},
                'eligible': eligible, 'selected': eligible,
                'reason': ('partner_weak_low_loyalty_and_relation_below_0_3'
                           if opportunistic_betrayal else
                           'relation_below_minus_0_4' if hostile_relation else
                           'betrayal_threshold_not_met')})
            if eligible:
                intents.append(BreakTreatyIntent(
                    nation_name=self.nation.name,
                    target_nation_name=partner.name,
                    treaty_type=tr.treaty_type,
                    submitted_turn=t,
                    regime_type=self.nation.regime_type
                ))

        # 5. Ideological Blocs & War Outbreak (M5.6)
        for other in other_nations:
            if diplomacy.are_at_war(self.nation.name, other.name):
                candidate_evaluations.append({
                    'policy': 'ideological_war', 'target': other.name,
                    'at_war': True, 'eligible': False, 'selected': False,
                    'reason': 'already_at_war'})
                continue
            rel = diplomacy.get_relation(self.nation.name, other.name)
            # Check if polarization threshold crossed (negative relation + regime opposition)
            regime_clash = (self.nation.regime_type == 'autocracy' and other.regime_type == 'democracy') or \
                           (self.nation.regime_type == 'democracy' and other.regime_type == 'autocracy')
            relation_gate = rel <= -0.7
            relative_strength = mil_strengths.get(other.name, 0.0)
            strength_gate = my_strength > relative_strength * 1.2
            eligible = relation_gate and regime_clash and strength_gate
            candidate_evaluations.append({
                'policy': 'ideological_war', 'target': other.name,
                'relation': rel, 'relation_threshold': -0.7,
                'relation_gate': relation_gate,
                'own_regime': self.nation.regime_type,
                'other_regime': other.regime_type,
                'regime_clash': regime_clash,
                'own_military_strength': my_strength,
                'other_military_strength': relative_strength,
                'strength_threshold_multiplier': 1.2,
                'strength_gate': strength_gate,
                'eligible': eligible, 'selected': eligible,
                'reason': ('hostile_relation_regime_clash_and_strength_advantage'
                           if eligible else
                           'relation_not_hostile_enough' if not relation_gate else
                           'no_autocracy_democracy_clash' if not regime_clash else
                           'insufficient_military_advantage')})
            if eligible:
                # Declare war
                intents.append(DeclareWarIntent(
                    nation_name=self.nation.name,
                    target_nation_name=other.name,
                    reason=f"Ideological confrontation ({self.nation.regime_type} vs {other.regime_type}) and border tension",
                    submitted_turn=t,
                    regime_type=self.nation.regime_type
                ))

        self._last_diplomacy_event_id = None
        if self.nation.tiles:
            from run_trace import emit
            self._last_diplomacy_event_id = emit(
                self.nation.tiles[0], kind='nation_diplomacy_evaluation',
                record_class='decision', phase='strategy',
                subject={'type': 'nation', 'id': self.nation.name},
                metric_id='diplomacy.ai_candidates',
                inputs={
                    'own_military_strength': my_strength,
                    'military_strengths': mil_strengths,
                    'candidate_evaluations': candidate_evaluations,
                    'proposed_intents': [
                        {'intent_type': type(intent).__name__,
                         'target': getattr(intent, 'target_nation_name', None),
                         'treaty_type': getattr(intent, 'treaty_type', None)}
                        for intent in intents],
                    'proposed_intent_count': len(intents)})

        return intents

    # ------------------------------------------------------------------
    # Main AI Turn Step
    # ------------------------------------------------------------------

    def evaluate_peace_offer(self, war, enemy, *, _trace_context=None) -> bool:
        """Accept a current-control ceasefire when it beats continued fighting."""
        trace_context = _war_ai_trace_context(
            self.nation, enemy, war, getattr(war.pending_offer, 'turn',
                                             war.declared_turn),
            shared=_trace_context)
        own = war.sides[self.nation.name]
        enemy_side = war.sides[enemy.name]
        lost_tiles = len(own.initial_tiles - {r.name for r in self.nation.tiles})
        gained_tiles = len(enemy_side.initial_tiles & {r.name for r in self.nation.tiles})
        own_power = effective_strength(self.nation)
        enemy_power = effective_strength(enemy)
        runway = supply_runway(self.nation)

        # The offered ceasefire makes no new regime demand.  Existing lost
        # territory is costly, while avoiding another unsupplied campaign has
        # immediate value.  An unfulfilled regime-change goal also costs the
        # attacker if it accepts early.
        accept_value = (0.25 + 0.35 * gained_tiles - 0.55 * lost_tiles
                        + (0.55 if runway < 2.0 else 0.0))
        has_unsecured_regime_change = (
            any(a.kind == 'regime_change' for a in own.aims)
            and not aim_secured(self.nation, enemy, own))
        if has_unsecured_regime_change:
            accept_value -= 1.25
        continue_value = (0.35 * own_power / max(1.0, own_power + enemy_power)
                          - 0.10 * min(3, own.recent_losses)
                          - (0.30 if runway < 2.0 else 0.0))
        accepted = accept_value >= continue_value + 0.10
        _emit_war_ai_trace(
            trace_context, kind='war_peace_offer_evaluation',
            nation=self.nation, enemy=enemy,
            metric_id='war.peace_offer_evaluation', unit='accepted',
            after=accepted,
            record_class='calculation',
            formula_id='war.peace_offer_acceptance.v1',
            inputs={
                'decision': 'accept_current_control_ceasefire',
                'lost_tiles': lost_tiles,
                'gained_tiles': gained_tiles,
                'own_effective_strength': own_power,
                'enemy_effective_strength': enemy_power,
                'own_power_share': own_power / max(1.0, own_power + enemy_power),
                'supply_runway_turns': runway,
                'low_supply_runway': runway < 2.0,
                'recent_losses': own.recent_losses,
                'aims': [{'kind': aim.kind, 'target': aim.target}
                         for aim in own.aims],
                'unsecured_regime_change_penalty_applied':
                    has_unsecured_regime_change,
                'accept_value_components': {
                    'base': 0.25,
                    'territory_gained': 0.35 * gained_tiles,
                    'territory_lost': -0.55 * lost_tiles,
                    'low_runway': 0.55 if runway < 2.0 else 0.0,
                    'unsecured_regime_change':
                        -1.25 if has_unsecured_regime_change else 0.0},
                'accept_value': accept_value,
                'continue_value_components': {
                    'relative_strength': 0.35 * own_power / max(
                        1.0, own_power + enemy_power),
                    'recent_losses': -0.10 * min(3, own.recent_losses),
                    'low_runway': -0.30 if runway < 2.0 else 0.0},
                'continue_value': continue_value,
                'required_advantage': 0.10,
                'acceptance_threshold': continue_value + 0.10,
                'decision_turn': trace_context.get('turn')
                    if trace_context else None})
        return accepted

    def choose_war_intent(self, war, enemy, t: int):
        trace_context = _war_ai_trace_context(self.nation, enemy, war, t)

        def record_choice(intent, reason, *, inputs=None, causes=None):
            if intent is None:
                selected = {'intent_type': None}
            elif isinstance(intent, MoveArmyIntent):
                selected = {'intent_type': type(intent).__name__,
                            'unit_id': intent.unit_id,
                            'from': intent.from_region, 'to': intent.to_region}
            elif isinstance(intent, RespondPeaceIntent):
                selected = {'intent_type': type(intent).__name__,
                            'target': intent.proposer_name,
                            'accept': intent.accept}
            elif isinstance(intent, ProposePeaceIntent):
                selected = {'intent_type': type(intent).__name__,
                            'target': intent.target_nation_name}
            else:
                selected = {'intent_type': type(intent).__name__}
            decision_inputs = dict(inputs or {})
            decision_inputs.update({'reason': reason, 'decision_turn': t,
                                    'war_declared_turn': war.declared_turn,
                                    'posture': war.sides[self.nation.name].posture})
            if trace_context is not None:
                decision_inputs['prior_operation_event_ids'] = list(
                    trace_context.get('event_ids', ()))
            _emit_war_ai_trace(
                trace_context, kind='war_ai_intent_decision',
                nation=self.nation, enemy=enemy, metric_id='war.ai_intent',
                unit='intent', after=selected, inputs=decision_inputs,
                cause_event_ids=causes)
            return intent

        side = war.sides[self.nation.name]
        offer = war.pending_offer
        if offer is not None:
            if offer.recipient == self.nation.name and t > offer.turn:
                evaluation_start = (len(trace_context.get('event_ids', ()))
                                    if trace_context is not None else 0)
                accepted = self.evaluate_peace_offer(
                    war, enemy, _trace_context=trace_context)
                causes = (trace_context.get('event_ids', [])[evaluation_start:]
                          if trace_context is not None else None)
                intent = RespondPeaceIntent(
                    self.nation.name, offer.proposer, accepted,
                    submitted_turn=t, regime_type=self.nation.regime_type)
                return record_choice(
                    intent, 'peace_offer_evaluation',
                    inputs={'offer_proposer': offer.proposer,
                            'offer_recipient': offer.recipient,
                            'offer_turn': offer.turn,
                            'offer_terms': offer.terms,
                            'accepted': accepted},
                    causes=causes)
            reason = ('offer_response_turn_not_elapsed'
                      if offer.recipient == self.nation.name else
                      'waiting_for_other_side_to_respond')
            return record_choice(None, reason, inputs={
                'offer_proposer': offer.proposer,
                'offer_recipient': offer.recipient,
                'offer_turn': offer.turn,
                'offer_terms': offer.terms})

        # Give the defender a response turn after declaration.
        if t <= war.declared_turn:
            return record_choice(None, 'post_declaration_response_turn', inputs={
                'minimum_action_turn': war.declared_turn + 1})
        secured = aim_secured(self.nation, enemy, side)
        exhausted = side.posture == 'culminated'
        offer_cooldown_elapsed = t - side.last_offer_turn >= 3
        if (secured or exhausted) and offer_cooldown_elapsed:
            intent = ProposePeaceIntent(self.nation.name, enemy.name,
                                        submitted_turn=t,
                                        regime_type=self.nation.regime_type)
            return record_choice(intent, 'aim_secured_or_offensive_culminated',
                                 inputs={'aim_secured': secured,
                                         'offensive_culminated': exhausted,
                                         'last_offer_turn': side.last_offer_turn,
                                         'peace_offer_cooldown_turns': 3,
                                         'cooldown_elapsed': True})

        if side.posture != 'viable':
            return record_choice(None, 'offensive_posture_not_viable', inputs={
                'aim_secured': secured, 'offensive_culminated': exhausted,
                'last_offer_turn': side.last_offer_turn,
                'peace_offer_cooldown_turns': 3,
                'cooldown_elapsed': offer_cooldown_elapsed})

        forecasts = attack_forecasts(self.nation, enemy, side)
        selected_forecast = bool(
            forecasts and forecasts[0]['progress'] > forecasts[0]['cost'] + 0.15)
        forecast_rows = [dict(row) for row in forecasts[:5]]
        omitted_forecasts = max(0, len(forecasts) - len(forecast_rows))
        forecast_inputs = {
            'attack_forecasts': forecast_rows,
            'forecast_count': len(forecasts),
            'omitted_forecast_count': omitted_forecasts,
            'attack_margin_threshold': 0.15,
            'selected_forecast_margin': (
                forecasts[0]['progress'] - forecasts[0]['cost']
                if forecasts else None)}
        if selected_forecast:
            best = forecasts[0]
            intent = MoveArmyIntent(self.nation.name, best['unit_id'],
                                    best['from'], best['to'],
                                    submitted_turn=t,
                                    regime_type=self.nation.regime_type)
            return record_choice(intent, 'best_attack_forecast_exceeds_cost_margin',
                                 inputs=forecast_inputs)
        reason = ('no_viable_attack_forecast' if not forecasts else
                  'best_attack_forecast_below_cost_margin')
        return record_choice(None, reason, inputs=forecast_inputs)

    def decide_turn(self, t: int, all_tiles: list, all_nations: list,
                    diplomacy: DiplomacySystem) -> list[object]:
        """Evaluate situations and submit strategic Intents for this turn."""
        from food_security import enact_nation_food_response
        food_responses = enact_nation_food_response(self.nation, t)
        food_emergency = any(row['emergency'] for row in food_responses)
        submitted = []
        treasury = self.nation.treasury()
        considered = [{'candidate': 'do_nothing', 'feasible': True, 'score': 0.0}]
        considered.extend({'candidate': 'food_security', **row}
                          for row in food_responses)

        # At most one active war decision per turn.  Peace replies precede
        # attack selection; the intent executor resolves accepted replies
        # before troop movements, regardless of nation iteration order.
        for war in diplomacy.wars_for(self.nation.name):
            enemy_name = war.enemy_of(self.nation.name)
            enemy = next((n for n in all_nations if n.name == enemy_name), None)
            if enemy is None:
                continue
            if any(isinstance(pending, (MoveArmyIntent, ProposePeaceIntent,
                                        RespondPeaceIntent)) and
                   getattr(pending, 'target_nation_name',
                           getattr(pending, 'proposer_name', enemy_name)) == enemy_name
                   for pending in self.nation.intents):
                continue
            intent = self.choose_war_intent(war, enemy, t)
            considered.append({'candidate': 'war_response', 'target': enemy_name,
                               'feasible': intent is not None,
                               'reason': 'active war and no pending response'})
            if intent is not None:
                self.nation.submit_intent(intent, t)
                submitted.append(intent)
                break

        # 1. Military Defense & Vulnerability Checks (M5.2)
        for tile in self.nation.tiles:
            vuln, reason = self.evaluate_tile_vulnerability(tile, all_nations, diplomacy)
            considered.append({'candidate': 'recruit_defense', 'tile': tile.name,
                               'score': vuln, 'feasible': vuln > 0.5 and treasury['total'] >= 30.0,
                               'reason': reason})
            if vuln > 0.5 and treasury['total'] >= 30.0:
                # Recruit local garrison / reinforcement
                intent = RecruitArmyIntent(
                    nation_name=self.nation.name,
                    region_name=tile.name,
                    soldier_count=15,
                    submitted_turn=t,
                    regime_type=self.nation.regime_type
                )
                self.nation.submit_intent(intent, t)
                submitted.append(intent)

        # 2. Diplomatic Intents (M5.4–M5.7)
        dip_intents = self.evaluate_diplomacy(all_nations, diplomacy, t)
        considered.append({'candidate': 'diplomacy', 'feasible': bool(dip_intents),
                           'reason': 'policy evaluation returned intents' if dip_intents else 'no diplomatic intent'})
        for intent in dip_intents:
            if food_emergency and isinstance(intent, DeclareWarIntent):
                considered.append({'candidate': 'declare_war', 'feasible': False,
                                   'reason': 'food emergency raises the cost of an offensive'})
                continue
            self.nation.submit_intent(intent, t)
            submitted.append(intent)

        # 3. Emergency Contractor Subsidies (Avert Navvy Layoffs & Riots)
        if treasury['total'] < 120.0:
            considered.append({'candidate': 'contractor_subsidy', 'feasible': False,
                               'reason': 'treasury below 120', 'treasury': treasury['total']})
        if treasury['total'] >= 120.0 and not food_emergency:
            for tile in self.nation.tiles:
                for proj in getattr(tile, 'construction_projects', []):
                    if proj.status == 'stalled' or (proj.contractor and proj.contractor.cash < 5.0):
                        considered.append({'candidate': 'contractor_subsidy', 'project': proj.project_id,
                                           'feasible': True, 'amount': 100.0})
                        sub_intent = SubsidizeContractorIntent(
                            nation_name=self.nation.name,
                            project_id=proj.project_id,
                            amount=100.0,
                            submitted_turn=t,
                            regime_type=self.nation.regime_type
                        )
                        self.nation.submit_intent(sub_intent, t)
                        submitted.append(sub_intent)
                        break

        # 4. Public Works Infrastructure Procurement (Respond to Contractor Lobbying & Bottlenecks)
        if treasury['total'] < 320.0 or submitted or food_emergency:
            considered.append({'candidate': 'public_works', 'feasible': False,
                               'reason': ('food emergency' if food_emergency else
                                          'treasury below 320' if treasury['total'] < 320.0
                                          else 'another intent already submitted')})
        if treasury['total'] >= 320.0 and len(submitted) == 0 and not food_emergency:
            for tile in self.nation.tiles:
                has_turnpike = any(b.name == 'turnpike_road' for b in getattr(tile, 'buildings', []))
                has_canal = any(b.name == 'barge_canal' for b in getattr(tile, 'buildings', []))
                has_proj = any(p.status in ('in_progress', 'stalled') for p in getattr(tile, 'construction_projects', []))
                if not has_proj:
                    target_recipe = None
                    if not has_turnpike:
                        target_recipe = 'turnpike_road'
                    elif not has_canal:
                        target_recipe = 'barge_canal'

                    if target_recipe:
                        considered.append({'candidate': 'public_works', 'tile': tile.name,
                                           'feasible': True, 'building': target_recipe})
                        build_intent = BuildIntent(
                            nation_name=self.nation.name,
                            region_name=tile.name,
                            building_type=target_recipe,
                            submitted_turn=t,
                            regime_type=self.nation.regime_type
                        )
                        self.nation.submit_intent(build_intent, t)
                        submitted.append(build_intent)
                        break

        # 5. Market-Driven Feudal Enclosure & Pasture Allocation
        if t < 3:
            considered.append({'candidate': 'enclose_commons', 'feasible': False,
                               'reason': 'turn below 3'})
        if t >= 3 and food_emergency:
            considered.append({'candidate': 'enclose_commons', 'feasible': False,
                               'reason': 'food emergency threatens current livelihoods'})
        if t >= 3 and not food_emergency:
            for tile in self.nation.tiles:
                if getattr(tile, 'food_enclosure_moratorium', False):
                    food_assessment = next((row for row in food_responses
                                            if row.get('tile') == tile.name), {})
                    considered.append({'candidate': 'enclose_commons', 'tile': tile.name,
                                       'feasible': False,
                                       'reason': 'food buffer is unsafe across the full crop cycle',
                                       'crop_cycle_turns': food_assessment.get('crop_cycle_turns'),
                                       'observed_crop_cycle_turns': food_assessment.get('observed_crop_cycle_turns'),
                                       'projected_crop_cycle_margin': food_assessment.get('projected_crop_cycle_margin'),
                                       'projected_crop_cycle_margin_with_commons': food_assessment.get('projected_crop_cycle_margin_with_commons'),
                                       'forecast_commons_cycle_food': food_assessment.get('forecast_commons_cycle_food'),
                                       'crop_cycle_meal_demand': food_assessment.get('crop_cycle_meal_demand'),
                                       'accessible_food_buffer': food_assessment.get('accessible_food_buffer')})
                    continue
                tenure = getattr(tile, 'tenure', None)
                if not tenure:
                    continue
                feudal = tenure.feudal_plots()
                if not feudal:
                    continue
                pe = tile.protest_energy_log[-1] if getattr(tile, 'protest_energy_log', None) else 0.0
                if pe < 4.5:
                    p_grain = tile.recipes.get(Goods.food, {}).get('price', 1.0)
                    p_wool = tile.recipes.get(Goods.wool, {}).get('price', 3.5)
                    # Enclosure triggered when grain >= 1.6 or wool >= 3.5
                    if p_grain >= 1.6 or p_wool >= 3.5 or (t % 5 == 0):
                        plot = feudal[0]
                        from enclosure import calculate_charter_fee
                        fee = calculate_charter_fee(plot)
                        lord = next((a for a in tile.agents if a.id == plot.lord_id), None)
                        if lord and lord.cash >= fee:
                            considered.append({'candidate': 'enclose_commons', 'tile': tile.name,
                                               'feasible': True, 'grain_price': p_grain,
                                               'wool_price': p_wool, 'protest_energy': pe,
                                               'lord_cash': lord.cash, 'charter_fee': fee})
                            # Dynamic Land Use: Pasture if wool price is strong vs grain
                            if (p_wool / max(0.5, p_grain)) >= 1.8:
                                plot.production_type = 'pasture'
                            else:
                                plot.production_type = 'arable'

                            from intents import EncloseCommonsIntent
                            intent = EncloseCommonsIntent(
                                nation_name=self.nation.name,
                                tile_name=tile.name,
                                plot_id=plot.plot_id,
                                submitted_turn=t,
                                regime_type=self.nation.regime_type
                            )
                            self.nation.submit_intent(intent, t)
                            submitted.append(intent)
                            break

        from run_trace import emit
        if self.nation.tiles:
            decision_id = emit(self.nation.tiles[0], kind='nation_ai_decision',
                 record_class='decision', phase='strategy',
                 subject={'type': 'nation', 'id': self.nation.name},
                 cause_event_ids=([self._last_diplomacy_event_id]
                                  if getattr(self, '_last_diplomacy_event_id', None)
                                  else None),
                 inputs={'treasury_total': treasury['total'],
                         'considered': considered,
                         'food_security': food_responses,
                         'selected': [type(intent).__name__ for intent in submitted],
                         'submitted_count': len(submitted)})
            for intent in submitted:
                intent._decision_event_id = decision_id
        return submitted

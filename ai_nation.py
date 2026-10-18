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
        score = 0.0
        recipes = getattr(tile, 'recipes', {})
        for g in [Goods.food, Goods.wood, Goods.furniture]:
            recipe = recipes.get(g, {})
            base_price = recipe.get('price', 10.0)
            mult = recipe.get('productivity_mult', 1.0)
            score += base_price * mult

        # Climate adjustment
        climate = getattr(tile, 'climate', 'temperate')
        if climate == 'cold':
            score *= 0.8
        elif climate == 'fertile':
            score *= 1.4

        # Native population base value
        pop = len(getattr(tile, 'agents', [])) + getattr(tile, 'wilderness_pop', 0)
        score += min(50.0, pop * 0.5)
        return score

    def score_bottleneck_relief(self, tile) -> float:
        """Calculate how much *tile* relieves this nation's resource bottlenecks (M5.1).

        Analyzes own tiles' demand_ratio_log and price_spread_log for shortages.
        """
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
        if avg_food_price > 15.0 and tile_recipes.get(Goods.food, {}).get('productivity_mult', 1.0) > 1.2:
            bonus += (avg_food_price - 10.0) * 3.0

        # If own wood is expensive (> $25) and candidate tile has wood advantage
        if avg_wood_price > 25.0 and tile_recipes.get(Goods.wood, {}).get('productivity_mult', 1.0) > 1.2:
            bonus += (avg_wood_price - 20.0) * 2.5

        return bonus

    def evaluate_candidate_tile(self, tile) -> tuple[float, str]:
        """Total desirability score for acquiring *tile* with explanation string."""
        terrain_score = self.score_terrain_value(tile)
        bottleneck_score = self.score_bottleneck_relief(tile)
        total = terrain_score + bottleneck_score
        reason = f"Terrain score: {terrain_score:.1f}, Bottleneck relief bonus: {bottleneck_score:.1f} (Total: {total:.1f})"
        return total, reason

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
        best_candidate = None
        best_score = -999.0
        best_plan = None

        # Find all adjacent non-owned tiles
        candidates = set()
        for own_tile in self.nation.tiles:
            for neighbor in own_tile.neighbors.values():
                if getattr(neighbor, 'owner_nation', None) is not self.nation and not getattr(neighbor, 'is_ocean', False) and getattr(neighbor, 'elevation', 0.0) >= 0.0:
                    candidates.add(neighbor)

        for tile in candidates:
            score, val_reason = self.evaluate_candidate_tile(tile)
            owner = getattr(tile, 'owner_nation', None)

            if owner is None:
                # Wilderness / unowned tile: settlement vector
                cost = 20.0
                net_score = score * self.personality['expansionist'] - cost * 0.1
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
                    plan = {
                        'tile': tile,
                        'mode': 'conquest',
                        'target_nation': owner.name,
                        'score': net_score,
                        'reason': f"Annex {tile.name} from {owner.name} by force ({val_reason})"
                    }
                else:
                    continue

            if plan['score'] > best_score and plan['score'] > 5.0:
                best_score = plan['score']
                best_plan = plan

        return best_plan

    # ------------------------------------------------------------------
    # M5.4–M5.7 Diplomacy, Alliances, Blocs & Betrayals
    # ------------------------------------------------------------------

    def evaluate_diplomacy(self, all_nations: list, diplomacy: DiplomacySystem,
                           t: int = 0) -> list[object]:
        """Generate diplomatic intents (alliances, trade pacts, betrayals, wars)."""
        intents = []
        treasury = self.nation.treasury()
        other_nations = [n for n in all_nations if n.name != self.nation.name]

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
            if other_str > my_strength * 1.4 and rel < 0.2:
                if other_str > max_threat_score:
                    max_threat_score = other_str
                    threat_nation = other

        # 2. Counterbalancing Alliance Formation (M5.5)
        if threat_nation is not None:
            for ally_cand in other_nations:
                if ally_cand.name == threat_nation.name:
                    continue
                # If ally candidate also faces threat from threat_nation and is not allied
                if not diplomacy.has_treaty(self.nation.name, ally_cand.name, TreatyType.DEFENSIVE_ALLIANCE.value):
                    rel = diplomacy.get_relation(self.nation.name, ally_cand.name)
                    if rel >= -0.1:  # willing to cooperate against common threat
                        intents.append(ProposeTreatyIntent(
                            nation_name=self.nation.name,
                            target_nation_name=ally_cand.name,
                            treaty_type=TreatyType.DEFENSIVE_ALLIANCE.value,
                            submitted_turn=t,
                            regime_type=self.nation.regime_type
                        ))
                        break

        # 3. Bilateral Trade Pacts (M5.4)
        for other in other_nations:
            if not diplomacy.has_treaty(self.nation.name, other.name, TreatyType.TRADE_PACT.value):
                rel = diplomacy.get_relation(self.nation.name, other.name)
                if rel >= 0.1:
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
                continue

            partner_str = mil_strengths.get(partner.name, 0.0)
            rel = diplomacy.get_relation(self.nation.name, partner.name)

            # Betrayal condition: partner is crippled (low military) while self has strong militarism
            # and low loyalty, or relations collapsed into negative
            if (partner_str < 10.0 and my_strength > 50.0 and self.personality['loyalty'] < 0.5 and rel < 0.3) or rel < -0.4:
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
                continue
            rel = diplomacy.get_relation(self.nation.name, other.name)
            # Check if polarization threshold crossed (negative relation + regime opposition)
            regime_clash = (self.nation.regime_type == 'autocracy' and other.regime_type == 'democracy') or \
                           (self.nation.regime_type == 'democracy' and other.regime_type == 'autocracy')
            
            if rel <= -0.7 and regime_clash and my_strength > mil_strengths.get(other.name, 0.0) * 1.2:
                # Declare war
                intents.append(DeclareWarIntent(
                    nation_name=self.nation.name,
                    target_nation_name=other.name,
                    reason=f"Ideological confrontation ({self.nation.regime_type} vs {other.regime_type}) and border tension",
                    submitted_turn=t,
                    regime_type=self.nation.regime_type
                ))

        return intents

    # ------------------------------------------------------------------
    # Main AI Turn Step
    # ------------------------------------------------------------------

    def evaluate_peace_offer(self, war, enemy) -> bool:
        """Accept a current-control ceasefire when it beats continued fighting."""
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
        if any(a.kind == 'regime_change' for a in own.aims) and not aim_secured(
                self.nation, enemy, own):
            accept_value -= 1.25
        continue_value = (0.35 * own_power / max(1.0, own_power + enemy_power)
                          - 0.10 * min(3, own.recent_losses)
                          - (0.30 if runway < 2.0 else 0.0))
        return accept_value >= continue_value + 0.10

    def choose_war_intent(self, war, enemy, t: int):
        side = war.sides[self.nation.name]
        offer = war.pending_offer
        if offer is not None:
            if offer.recipient == self.nation.name and t > offer.turn:
                return RespondPeaceIntent(
                    self.nation.name, offer.proposer,
                    self.evaluate_peace_offer(war, enemy),
                    submitted_turn=t, regime_type=self.nation.regime_type)
            return None

        # Give the defender a response turn after declaration.
        if t <= war.declared_turn:
            return None
        secured = aim_secured(self.nation, enemy, side)
        exhausted = side.posture == 'culminated'
        if (secured or exhausted) and t - side.last_offer_turn >= 3:
            return ProposePeaceIntent(self.nation.name, enemy.name,
                                      submitted_turn=t,
                                      regime_type=self.nation.regime_type)

        if side.posture != 'viable':
            return None
        forecasts = attack_forecasts(self.nation, enemy, side)
        if forecasts and forecasts[0]['progress'] > forecasts[0]['cost'] + 0.15:
            best = forecasts[0]
            return MoveArmyIntent(self.nation.name, best['unit_id'],
                                  best['from'], best['to'],
                                  submitted_turn=t,
                                  regime_type=self.nation.regime_type)
        return None

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
                 inputs={'treasury_total': treasury['total'],
                         'considered': considered,
                         'food_security': food_responses,
                         'selected': [type(intent).__name__ for intent in submitted],
                         'submitted_count': len(submitted)})
            for intent in submitted:
                intent._decision_event_id = decision_id
        return submitted

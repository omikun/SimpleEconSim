"""Time-limited, named state concessions that change actual buyer access."""
from goods import Goods

CHARTER_TYPES = frozenset({'exclusive_buying', 'exclusive_processing', 'exclusive_route'})


def submit_concession_petition(sponsor, region, good, charter_type, fee, term_turns, turn):
    if (charter_type not in CHARTER_TYPES or good not in getattr(region, 'recipes', {})
            or sponsor.cash < fee or getattr(region, 'gov', None) is None):
        return None
    government = getattr(region.gov, 'agent', None)
    if government is None:
        return None
    if not hasattr(region, 'concession_petitions'):
        region.concession_petitions = []
    if any(p['status'] == 'proposed' and p['good'] == getattr(good, 'value', str(good))
           and p['type'] == charter_type for p in region.concession_petitions):
        return None
    fee, term_turns = max(0.0, float(fee)), max(1, int(term_turns))
    sponsor.cash -= fee
    government.cash += fee
    petition = {'id': int(getattr(region, '_next_concession_id', 1)),
                'good': getattr(good, 'value', str(good)), 'type': charter_type,
                'sponsor_id': sponsor.id, 'fee': fee, 'requested_turn': int(turn),
                'decision_turn': int(turn) + 1, 'term_turns': term_turns,
                'status': 'proposed'}
    competitors = [a.id for a in getattr(region, 'agents', []) if a.id != sponsor.id
                   and getattr(a, 'alive', True) and (getattr(a, 'is_corporation', False)
                   or getattr(a, 'is_trader', False))]
    petition['review_brief'] = {
        'beneficiaries': [sponsor.id, getattr(getattr(region, 'gov', None), 'agent', sponsor).id],
        'exposed_growers': [a.id for a in getattr(region, 'agents', [])
                            if getattr(a, 'alive', True) and a.output == good
                            and not getattr(a, 'is_corporation', False)],
        'restricted_competitors': competitors,
        'expected_effect': ('fewer rival bids may lower grower receipts' if charter_type == 'exclusive_buying'
                            else 'rival processors may lose input access' if charter_type == 'exclusive_processing'
                            else 'route rivals may be delayed; delivered supply may cost more'),
        'public_tradeoff': 'application fee enters treasury; food supply and legitimacy may fall',
        'alternatives': ['leave auction competitive', 'fund grower advances',
                         'buy public reserves', 'improve routes or production'],
        'uncertainty': 'high: supplier choices, leakage, and seasonal output vary',
    }
    region._next_concession_id = petition['id'] + 1
    region.concession_petitions.append(petition)
    from run_trace import emit
    emit(region, kind='market_concession_petition', record_class='decision',
         subject={'type': 'agent', 'id': sponsor.id}, metric_id='market.charter_petition',
         unit='petition', after=petition['id'], formula_id='charter.petition_fee.v1',
         inputs=petition)
    return petition


def decide_concession_petitions(region, turn):
    government = getattr(getattr(region, 'gov', None), 'agent', None)
    if not hasattr(region, 'concession_petitions'):
        region.concession_petitions = []
    events = []
    for petition in sorted(region.concession_petitions, key=lambda p: p['id']):
        if petition['status'] != 'proposed' or petition['decision_turn'] > turn:
            continue
        if petition.get('player_review') and not petition.get('player_decision'):
            petition['status'] = 'expired'
            events.append({'turn': int(turn), 'petition_id': petition['id'],
                           'status': 'expired', 'good': petition['good'],
                           'type': petition['type'], 'sponsor_id': petition['sponsor_id'],
                           'reason': 'player review deadline passed'})
            continue
        good = next((g for g in region.recipes
                     if getattr(g, 'value', str(g)) == petition['good']), None)
        sponsors = next((a for a in region.agents if a.id == petition['sponsor_id']), None)
        suppliers = sum(1 for a in region.agents if getattr(a, 'alive', True)
                        and a.output == good and not getattr(a, 'is_corporation', False))
        legitimacy = float(getattr(region, 'government_legitimacy', .5))
        # The decision weighs treasury solvency, legitimacy, supplier exposure,
        # and visible domestic food pressure. No price is set by the charter.
        food_pressure = max(0.0, float(getattr(region, 'unrest_level', 0.0)))
        job_count = len(getattr(sponsors, 'employees', [])) if sponsors else 0
        good_price = float(region.recipes.get(good, {}).get('price', 0.0)) if good is not None else 0.0
        food_cost = max(0.0, good_price - 1.25) if petition['good'] == Goods.food.value else 0.0
        strategic = .15 if petition['good'] in (Goods.food.value, Goods.iron.value, Goods.coal.value) else 0.05
        fiscal = .15 if government is not None and government.cash >= petition['fee'] else -.10
        public_score = (.30 * legitimacy + .05 * min(1.0, job_count / 10.0) + strategic + fiscal
                        - .12 * max(0, suppliers - 2) - .25 * food_cost - .30 * food_pressure)
        approved = (petition.get('player_decision') == 'approve' if petition.get('player_decision') else
                    bool(government and sponsors and government.cash >= 0
                         and legitimacy >= .35 and suppliers <= 8
                         and (petition['good'] != Goods.food.value or food_pressure < .75)
                         and public_score >= .15))
        petition['status'] = 'enacted' if approved else 'rejected'
        if approved:
            if not hasattr(region, 'market_charters'):
                region.market_charters = []
            charter = {k: petition[k] for k in ('id', 'good', 'type', 'sponsor_id', 'term_turns')}
            charter.update({'start_turn': int(turn), 'expiry_turn': int(turn) + petition['term_turns'],
                            'enforcement': max(.0, min(1.0, float(getattr(region, 'concession_enforcement', .65)))),
                            'status': 'active'})
            region.market_charters.append(charter)
        else:
            charter = None
        event = {'turn': int(turn), 'petition_id': petition['id'], 'status': petition['status'],
                 'good': petition['good'], 'type': petition['type'],
                 'sponsor_id': petition['sponsor_id'], 'supplier_count': suppliers,
                 'legitimacy': legitimacy, 'food_pressure': food_pressure,
                 'public_interest_score': round(public_score, 4),
                 'decision_basis': ('player' if petition.get('player_decision') else 'government_ai'),
                 'term_turns': petition['term_turns'], 'charter': charter}
        region.concession_events = (getattr(region, 'concession_events', []) + [event])[-500:]
        events.append(event)
    for charter in getattr(region, 'market_charters', []):
        if charter.get('status') != 'active':
            continue
        opposition = float(charter.get('opposition', 0.0))
        unrest = float(getattr(region, 'unrest_level', 0.0))
        expired = int(charter.get('expiry_turn', 0)) <= turn
        contested = opposition >= 18.0 or unrest >= .95
        if expired or contested:
            charter['status'] = 'expired' if expired else 'repealed'
            event = {'turn': int(turn), 'charter_id': charter['id'], 'status': charter['status'],
                     'reason': 'term_expired' if expired else 'opposition_or_unrest',
                     'opposition': opposition, 'unrest': unrest,
                     'good': charter['good'], 'type': charter['type']}
            region.concession_events.append(event)
            events.append(event)
    from run_trace import emit
    for event in events:
        emit(region, kind='market_concession_decision', record_class='outcome',
             subject={'type': 'charter', 'id': event.get('petition_id', event.get('charter_id'))},
             metric_id='market.charter_status', unit='status', after=event['status'],
             formula_id='charter.public_interest_screen.v1', inputs=event)
    return events


def filter_chartered_bids(region, good, bid_rows, turn):
    """Restrict local bids under active charters; weak enforcement leaks trade."""
    charters = [c for c in getattr(region, 'market_charters', [])
                if c.get('status') == 'active' and c.get('good') == getattr(good, 'value', str(good))
                and c.get('start_turn', 0) <= turn < c.get('expiry_turn', 0)]
    if not charters:
        return bid_rows
    agents = {a.id: a for a in getattr(region, 'agents', [])}
    excluded = set()
    governing_type = None
    chosen = sorted(charters, key=lambda c: c['id'])[0]
    governing_type = chosen['type']
    if governing_type == 'exclusive_route':
        return bid_rows
    authorized_id = chosen['sponsor_id']
    enforcement = max(0.0, min(1.0, float(chosen.get('enforcement', .65))))
    allowed = []
    for row in bid_rows:
        buyer = row['agent']
        if buyer.id == authorized_id:
            allowed.append(row)
            continue
        prohibited = (governing_type == 'exclusive_buying' or
                      (governing_type == 'exclusive_processing' and
                       getattr(buyer, 'is_corporation', False) and
                       getattr(buyer, 'output', None) in region.recipes and
                       region.recipes[buyer.output].get('input') == good))
        if not prohibited:
            allowed.append(row)
            continue
        leaked = int(int(row['quantity']) * (1.0 - enforcement))
        if leaked > 0:
            allowed.append({**row, 'quantity': leaked})
        excluded.add(buyer.id)
    if excluded:
        allowed_quantity = {row['agent'].id: int(row['quantity']) for row in allowed}
        suppressed_units = sum(int(row['quantity']) - allowed_quantity.get(row['agent'].id, 0)
                               for row in bid_rows)
        chosen['opposition'] = float(chosen.get('opposition', 0.0)) + max(1.0, suppressed_units / 3.0)
        from run_trace import emit
        emit(region, kind='market_charter_enforcement', record_class='calculation',
             subject={'type': 'charter', 'id': chosen['id']},
             metric_id='market.excluded_buyer_orders', unit='orders', after=len(excluded),
             formula_id='charter.enforcement_leakage.v1',
             inputs={'good': getattr(good, 'value', str(good)), 'charter_type': governing_type,
                     'authorized_buyer_id': authorized_id, 'excluded_buyer_ids': sorted(excluded),
                     'enforcement': enforcement, 'leakage_fraction': 1.0 - enforcement,
                     'opposition_after': chosen['opposition'],
                     'submitted_quantity': sum(int(r['quantity']) for r in bid_rows),
                     'eligible_quantity': sum(int(r['quantity']) for r in allowed)})
    return allowed

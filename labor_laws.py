"""Petitions and delayed regional decisions for labor laws."""


LAW_NAMES = frozenset({'vagrancy', 'gathering_restriction', 'quit_penalty', 'wage_cap'})


def submit_law_petition(sponsor, region, law, fee, turn):
    if law not in LAW_NAMES or sponsor.cash < fee or getattr(region, 'gov', None) is None:
        return None
    gov = getattr(region.gov, 'agent', None)
    if not hasattr(region, 'labor_law_petitions'):
        region.labor_law_petitions = []
    if not hasattr(region, 'labor_laws'):
        region.labor_laws = {}
    if gov is None or any(p['law'] == law and p['status'] == 'proposed'
                          for p in getattr(region, 'labor_law_petitions', [])):
        return None
    sponsor.cash -= fee
    gov.cash += fee
    petition = {'id': int(getattr(region, '_next_law_petition_id', 1)),
                'law': law, 'sponsor_id': sponsor.id, 'fee': float(fee),
                'requested_turn': int(turn), 'decision_turn': int(turn) + 1,
                'status': 'proposed'}
    region._next_law_petition_id = petition['id'] + 1
    region.labor_law_petitions.append(petition)
    return petition


def decide_labor_laws(region, turn):
    if not hasattr(region, 'labor_law_petitions'):
        region.labor_law_petitions = []
    gov = getattr(getattr(region, 'gov', None), 'agent', None)
    events = []
    for petition in sorted(region.labor_law_petitions, key=lambda p: p['id']):
        if petition['status'] != 'proposed' or petition['decision_turn'] > turn:
            continue
        # Conservative deterministic approval: only a solvent government with
        # adequate institutional legitimacy accepts a coercive law.
        legitimacy = float(getattr(region, 'government_legitimacy', 0.5))
        approved = gov is not None and gov.cash >= 0 and legitimacy >= 0.5
        petition['status'] = 'enacted' if approved else 'rejected'
        if approved:
            region.labor_laws[petition['law']] = 'enacted'
            if petition['law'] == 'vagrancy':
                region.vagrancy_law_active = True
            if petition['law'] == 'gathering_restriction':
                from livelihood_access import effective_access
                for person_id, rights in getattr(region, 'access_rights', {}).items():
                    person = next((a for a in region.agents if a.id == person_id), None)
                    if person is None:
                        continue
                    for right in rights:
                        if right.resource == 'commons_food':
                            right.legal_share = 0.0
                            if int(getattr(region, 'police_employed', 0)) > 0:
                                right.usable_share = 0.0
            if petition['law'] == 'wage_cap':
                region.statute_of_laborers = True
                region.wage_cap = 1.50
                for firm in region.agents:
                    if getattr(firm, 'is_corporation', False):
                        firm.wage = min(float(getattr(firm, 'wage', 0.0)), region.wage_cap)
        events.append({'turn': turn, 'law': petition['law'], 'petition_id': petition['id'],
                       'status': petition['status'], 'sponsor_id': petition['sponsor_id']})
    region.labor_law_events = (getattr(region, 'labor_law_events', []) + events)[-200:]
    return events


def repeal_law(region, law):
    if law not in LAW_NAMES or getattr(region, 'labor_laws', {}).get(law) != 'enacted':
        return False
    region.labor_laws[law] = 'repealed'
    if law == 'vagrancy':
        region.vagrancy_law_active = False
    if law == 'wage_cap':
        region.statute_of_laborers = False
    if law == 'gathering_restriction':
        for rights in getattr(region, 'access_rights', {}).values():
            for right in rights:
                if right.resource == 'commons_food':
                    right.legal_share = max(right.legal_share, right.usable_share)
    return True

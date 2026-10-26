from enum import Enum, auto

def make_enum(name, values):
    return Enum(name, {v: i for i, v in enumerate(values)})

Resources = make_enum('Resources',
                      ['wood',
                       'food',
                       'metal',
                       'oil',
                       'coal',
                       'gold',
                       'diamond',
                       'chemical',
                       'rare_earth',
                       'electronics'
                       ])

Threats = make_enum('Threats', 
                  ['war', 
                   'coup', 
                   'embargo',
                   'blockade',
                   'tariff',
                   'price_hike',
                   'financial' ])
print(Threats.war, Threats.financial)

Policies = make_enum('Policies',
                    ['declare_war',
                     'war_invade'
                     'send_money',
                     'send_weapons',
                     'send_troops',
                     'propose_alliance',
                     'break_alliance',
                     'embargo',
                     'negotiate_trade'])

Actions = make_enum('Actions',
                    ['move_troops',
                     'attack_region',
                     'request_war_approval',
                     'spread_propaganda',
                     'pressure_congress',
                     'send_covert_op',
                     'reallocate_funding',
                     'declare_intention_goodwill',
                     'declare_intention_hostile',
                     'backchannel_inquire_alliance',
                     'backchannel_inquire_trade',
                     'backchannel_trade'])

def package_action(action, from_entity, to_entity):
    return {'action':action, 'with': from_entity, 'against': to_entity}

ThreatResponse = {Threats.war: [Policies.propose_alliance, Policies.declare_war, Policies.negotiate_trade],
                  Threats.coup: [Policies.propose_alliance, Policies.declare_war],
                  Threats.embargo: [Policies.propose_alliance, Policies.declare_war, Policies.embargo, Policies.negotiate_trade],
                  Threats.blockade: [Policies.declare_war, Policies.negotiate_trade],
                  Threats.tariff: [Policies.negotiate_trade],
                  Threats.price_hike: [Policies.negotiate_trade],
                  Threats.financial: [Policies.propose_alliance, Policies.break_alliance, Policies.embargo, Policies.negotiate_trade]
                  }
                  

# in order for country to access resource (in a foreign country)
# these conditions must be met
# (if not met, queue actions for consideration to alleviate them):

# trade country must exist and be soverign
    # anything that threatens soverignty or existence must be addressed
        # send military aid to country
        # send troops
        # declare war on their enemy
        # form larger alliance coalition
        # get agreement from aggressor to maintain trade after war
# must have trade relation with said country
    # be on friendly or neutral terms, if not
        # propose peace
        # send gifts
        # propose alliance
        # suggest trade
# consider tariff situation
    # retaliate with tariffs
    # suggest better trading conditions
# consider exchange rate situation
    # cut off trade
    # denounce currency manipulation
    # seek alliance to strangle this nation
    # offer something they want that doesn't cost you as much
# must accept self.currency 
# or self must be able to access the currency the resource is denominated in
# must have physical transport with said country
# not obstructed by any other entities
# must have transport infra

class Relation:
    def __init__(self):
        self.importance = 0
        self.trades = []
        self.tension = 0    # incr if near by and or have potential to be a threat (large military, big economy, or allied with a threat)
        self.threatened = 0 # incr if made an aggresive move recently
    
class Nation:
    def __init__(self, nname, pop, resources):
        self.name = nname
        self.population = pop
        self.resources = resources
        self.allies = []
        self.relations = []
        self.imports = []
        self.exports = []
        self.action_queues = []

    def threatened(self, action, r):
        #if any of these are true return true
        #war with country of resource origin threatens access
        threats = []
        if r in self.resources:
            pass
            # if import, what fraction of resources is sourced from this nation vs all nations?
            # if export, what fraction of export in this resource does this country buy?
            # if fraction high enough, 
            threats.append(Threats.war_indirect)
        #destruction of government
        #does not want to trade with self
        #destroys or erode relationship with origin country
        #raises tariffs
        #appreciate exchange rates
        #not accept self.currency or makes r.denominated_currency inaccessible
        #closes harbor or station to self
        #obstructs convoy
        #denies or damages transport infra  
        return threats
    
    def assessment(self, action):
        for r in self.resources:
            threats = self.threatened(action, r)
            if threats is not []:
                for threat in threats:
                    self.action_queues.append(ThreatResponse[threat])
                    
    def populate_actions(self):
        #consider all possible actions
        #invalidate impossible or not beneficial actions
        #rank them by order of importance
        #pick top three valid actions
        return

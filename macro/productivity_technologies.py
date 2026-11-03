"""Production applications grounded in real machinery and husbandry.

Multipliers are game balance values, not empirical productivity estimates.
Goods aggregate cultivation, processing and finishing into one commodity flow.
"""
from goods import Goods

PRODUCTION_GOODS = tuple(g for g in Goods if g not in (Goods.gov, Goods.none))
CROP_GOODS = (Goods.food, Goods.cotton, Goods.tobacco, Goods.sugar, Goods.tea)
AGRONOMY_LEARNING = {g: 0.015 for g in (*CROP_GOODS, Goods.wool)}
MANUFACTURING_LEARNING = {
    Goods.wood: 0.02, Goods.furniture: 0.035, Goods.cloth: 0.025,
    Goods.fine_textiles: 0.035, Goods.iron_ore: 0.02, Goods.iron: 0.035,
    Goods.coal: 0.02, Goods.nitrates: 0.025, Goods.porcelain: 0.035, Goods.rum: 0.025,
    Goods.prepared_food: 0.025,
    Goods.cotton: 0.01, Goods.sugar: 0.01, Goods.tea: 0.01, Goods.tobacco: 0.01,
}

SOURCES = {
    'steam': 'https://collection.sciencemuseumgroup.org.uk/objects/co50985',
    'farms': 'https://www.fao.org/interactive/agricultural-mechanization/en/',
    'breeding': 'https://www.fao.org/animal-genetics/background/why-is-ag-important/en/',
    'shearing': 'https://www.worksafe.govt.nz/topic-and-industry/agriculture/working-with-animals/working-with-sheep/safe-sheep-shearing-gpg/',
    'distilling': 'https://www.scotchwhiskyexperience.co.uk/about/about-whisky/whisky-making/',
    'forestry': 'https://www.iso.org/cms/%20render/live/en/sites/isoorg/contents/data/standard/05/08/50880.html',
    'mining': 'https://www.cdc.gov/niosh/mining/topics/machinery-struck-by-injuries.html',
    'industry': 'https://www.energy.gov/cmei/ito/industrial-efficiency-technologies',
    'cotton': 'https://www.ars.usda.gov/southeast-area/stoneville-ms/cotton-ginning-research/docs/what-is-a-cotton-gin/',
    'weaving': 'https://www.si.edu/spotlight/punch-cards',
    'pottery': 'https://collection.sciencemuseumgroup.org.uk/objects/co24090',
    'sugar': 'https://www.cirad.fr/en/our-activities-our-impact/tropical-value-chains/sugarcane/plant-and-uses',
    'tea': 'https://agritech.tnau.ac.in/postharvest/pht_plantationcrop_tea.html',
    'tobacco': 'https://craven.ces.ncsu.edu/flue-cured-tobacco-curing-practices/',
}


def expand_catalog(catalog, technology, domains, resources, food_pressure, wage_pressure):
    """Extend the existing tree through its normal discovery/install/refine path."""
    # Correct old target mismatches and make existing infrastructure productive.
    updates = {
        'bloomery_iron': ({Goods.wood: 1.25, Goods.iron: 1.25},
            'Bloomery smelting and durable iron tools improve ironworking and timber cutting.', 'industry'),
        'fluvial_watermills': ({Goods.food: 1.20, Goods.prepared_food: 1.20, Goods.wood: 1.35},
            'Water-powered gristmills and sawmills improve grain processing and sawn timber output.', 'steam'),
        'gunpowder_blasting': ({Goods.iron_ore: 1.30, Goods.coal: 1.30, Goods.nitrates: 1.30},
            'Controlled rock blasting opens workings and improves mineral extraction.', 'mining'),
        'deep_navigation': ({Goods.transport: 1.25},
            'Improved navigation and larger cargo vessels increase transport-service productivity.', 'industry'),
        'turnpike_trusts': ({Goods.transport: 1.25},
            'Maintained road surfaces improve haulage alongside their route-friction benefits.', 'industry'),
        'barge_canals': ({Goods.transport: 1.35},
            'Canals and pound locks improve bulk haulage alongside their route-friction benefits.', 'industry'),
        'mechanized_textiles': ({Goods.cloth: 1.40, Goods.fine_textiles: 1.20},
            'Mechanical carding, spinning and shuttle weaving increase cloth and textile finishing output.', 'weaving'),
        'coal_coking': ({Goods.iron: 1.50},
            'Coke-fired blast furnaces increase smelting output by replacing scarce charcoal.', 'industry'),
        'steam_engines': ({Goods.furniture: 1.50},
            'Installed line-shaft steam power drives equipped furniture machinery. Other tasks '
            'require their own compatible application, such as mine pumping or powered looms.', 'steam'),
        'bessemer_steel': ({Goods.iron: 1.50},
            'Bessemer steelmaking improves metal output while supporting stronger rails and machinery.', 'industry'),
        'mechanized_looms': ({Goods.cloth: 1.50, Goods.fine_textiles: 1.40},
            'Steam-powered looms increase cloth and garment output; the benefit applies to textiles.', 'weaving'),
        'petroleum_refining': ({Goods.transport: 1.50},
            'Refined motor fuels support productive motorized freight and diesel equipment.', 'industry'),
        'dynamo_electrification': ({g: 1.35 for g in PRODUCTION_GOODS},
            'Installed electric drives power machinery, pumps, fans and handling equipment across production.', 'industry'),
        'microelectronics': ({g: 1.25 for g in PRODUCTION_GOODS},
            'Installed sensing, numerical control and process automation improve production across professions.', 'industry'),
    }
    for tid, (bonuses, description, source) in updates.items():
        tech = catalog[tid]
        tech.production_modifiers = {g.value: value for g, value in bonuses.items()}
        tech.description = description
        tech.source_urls = [SOURCES[source]]

    # id, label, era, domain, prerequisites, resources, affected goods, description, source
    specs = [
        ('seed_drills', 'Seed Drills & Row Cultivation', 2, 'AGRONOMY', ['bloomery_iron'],
         ['ARABLE_SILT', 'IRON_ORE'], {Goods.food: 1.30},
         'Metered seed placement and row cultivation improve field-labor productivity.', 'farms'),
        ('selective_livestock_breeding', 'Selective Sheep Breeding & Flock Husbandry', 1, 'AGRONOMY', [],
         ['PASTURE_FLAX'], {Goods.wool: 1.25},
         'Flock selection, feeding and husbandry improve marketable wool per unit of work.', 'breeding'),
        ('mechanical_shearing', 'Mechanical Sheep Shearing', 3, 'AGRONOMY', ['selective_livestock_breeding', 'bloomery_iron'],
         ['PASTURE_FLAX', 'IRON_ORE'], {Goods.wool: 1.40},
         'Powered reciprocating shears improve wool-harvest throughput.', 'shearing'),
        ('mechanized_harvesting', 'Tractors & Crop-Specific Harvesters', 4, 'AGRONOMY', ['seed_drills', 'petroleum_refining'],
         ['ARABLE_SILT', 'CRUDE_PETROLEUM'], {g: 1.40 for g in CROP_GOODS},
         'Tractors, combines, cotton pickers, cane harvesters and crop-specific cutters reduce field labor.', 'farms'),
        ('precision_machine_tools', 'Precision Lathes, Planers & Interchangeable Parts', 3, 'MANUFACTURING', ['steam_engines', 'bloomery_iron'],
         ['IRON_ORE'], {Goods.furniture: 1.35, Goods.iron: 1.25},
         'Powered metal lathes and woodworking planers improve repeatable parts and joinery.', 'industry'),
        ('mechanized_forestry', 'Chainsaws, Cable Logging & Skidders', 4, 'MANUFACTURING', ['petroleum_refining', 'fluvial_watermills'],
         ['TIMBER', 'CRUDE_PETROLEUM'], {Goods.wood: 1.50},
         'Purpose-built felling, extraction and log-handling equipment increases timber output.', 'forestry'),
        ('mine_pumping_hoists', 'Steam Mine Pumps & Winding Engines', 3, 'MANUFACTURING', ['steam_engines', 'gunpowder_blasting'],
         ['IRON_ORE', 'COAL_SEAM'], {g: 1.40 for g in (Goods.iron_ore, Goods.coal, Goods.nitrates)},
         'Drainage pumps and winding engines make deeper mineral workings productive.', 'steam'),
        ('mechanized_mining', 'Powered Drills, Cutters & Mine Conveyors', 4, 'MANUFACTURING', ['mine_pumping_hoists', 'dynamo_electrification'],
         ['IRON_ORE', 'RARE_MINERALS'], {g: 1.60 for g in (Goods.iron_ore, Goods.coal, Goods.nitrates)},
         'Powered drilling, continuous cutting and conveyors increase mineral-extraction throughput.', 'mining'),
        ('cotton_ginning', 'Roller & Saw Cotton Gins', 2, 'MANUFACTURING', ['bloomery_iron'],
         ['PASTURE_FLAX'], {Goods.cotton: 1.40},
         'Mechanical lint separation and cleaning increase marketable cotton processing per worker.', 'cotton'),
        ('jacquard_weaving', 'Jacquard Pattern Weaving', 3, 'MANUFACTURING', ['mechanized_textiles'],
         ['PASTURE_FLAX'], {Goods.fine_textiles: 1.50, Goods.cloth: 1.15},
         'Pattern-controlled looms reduce the labor needed for complex woven fabrics.', 'weaving'),
        ('pottery_wheels_kilns', 'Pottery Wheels & Controlled-Draft Kilns', 1, 'MANUFACTURING', [],
         ['TIMBER'], {Goods.porcelain: 1.30},
         'Wheel forming and controlled firing improve ceramic throughput and usable yield.', 'pottery'),
        ('continuous_ceramic_kilns', 'Continuous Ceramic Kilns & Process Control', 4, 'MANUFACTURING', ['pottery_wheels_kilns', 'dynamo_electrification'],
         ['COAL_SEAM'], {Goods.porcelain: 1.50},
         'Continuous firing, controlled heat and mechanized handling improve ceramic production.', 'industry'),
        ('roller_sugar_mills', 'Roller Sugar Mills & Juice Processing', 2, 'MANUFACTURING', ['fluvial_watermills'],
         ['TIMBER'], {Goods.sugar: 1.35},
         'Powered crushing rollers and controlled juice processing improve recoverable sugar.', 'sugar'),
        ('tea_rolling_drying', 'Mechanical Tea Rolling & Drying', 3, 'MANUFACTURING', ['steam_engines'],
         ['TIMBER'], {Goods.tea: 1.35},
         'Rolling machinery, hot-air drying and grading improve saleable tea throughput.', 'tea'),
        ('tobacco_curing', 'Controlled Tobacco Curing & Leaf Handling', 3, 'AGRONOMY', ['bloomery_iron'],
         ['TIMBER'], {Goods.tobacco: 1.30},
         'Controlled airflow, temperature and humidity reduce curing losses and handling work.', 'tobacco'),
        ('column_distillation', 'Continuous Column Distillation', 3, 'MANUFACTURING', ['steam_engines'],
         ['IRON_ORE'], {Goods.rum: 1.45},
         'Continuous vapor-liquid separation and heat integration improve spirit throughput.', 'distilling'),
    ]
    for tid, name, era, domain, prerequisites, deposits, bonuses, description, source in specs:
        catalog[tid] = technology(
            tech_id=tid, name=name, era=era, domain=getattr(domains, domain),
            description=description, base_xp_required=250 + era * 250,
            required_techs=prerequisites,
            required_resources=[getattr(resources, r) for r in deposits],
            production_modifiers={g.value: value for g, value in bonuses.items()},
            bottleneck_evaluator=food_pressure if domain == 'AGRONOMY' else wage_pressure,
            source_urls=[SOURCES[source]])

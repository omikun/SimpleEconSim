from enum import IntEnum, auto

class Goods(IntEnum):
    food = auto()
    wood = auto()
    furniture = auto()
    transport = auto()
    gov = auto()
    wool = auto()
    cloth = auto()
    nitrates = auto()
    cotton = auto()
    iron_ore = auto()
    iron = auto()
    coal = auto()
    tobacco = auto()
    sugar = auto()
    tea = auto()
    fine_textiles = auto()
    porcelain = auto()
    rum = auto()
    foreign_luxuries = auto()
    none = auto()


# Profession display characters (one per Goods value)
profession = {
    Goods.food: 'F',
    Goods.wood: 'W',
    Goods.furniture: 'C',
    Goods.transport: 'P',
    Goods.gov: 'G',
    Goods.wool: 'S',             # Shepherd / Grazier
    Goods.cloth: 'T',            # Weaver / Textilist
    Goods.nitrates: 'N',         # Nitrate Miner / Guano Digger
    Goods.cotton: 'O',           # Cotton Farmer / Planter
    Goods.iron_ore: 'I',         # Iron Ore Miner
    Goods.iron: 'B',             # Blacksmith / Ironworker
    Goods.coal: 'K',             # Collier / Coal Miner
    Goods.tobacco: 'Y',          # Tobacco Planter
    Goods.sugar: 'U',            # Sugar Cultivator
    Goods.tea: 'E',              # Tea Harvester
    Goods.fine_textiles: 'X',    # Master Tailor / Silk Weaver
    Goods.porcelain: 'Z',        # Master Potter / Ceramist
    Goods.rum: 'V',              # Distiller / Vintner
    Goods.foreign_luxuries: 'L', # Luxury Merchant
    Goods.none: '-',
}


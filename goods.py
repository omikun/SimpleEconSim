from enum import IntEnum, auto

class Goods(IntEnum):
    food = auto()
    wood = auto()
    furniture = auto()
    transport = auto()
    gov = auto()
    wool = auto()
    cloth = auto()
    none = auto()


# Profession display characters (one per Goods value)
profession = {
    Goods.food: 'F',
    Goods.wood: 'W',
    Goods.furniture: 'C',
    Goods.transport: 'P',
    Goods.gov: 'G',
    Goods.wool: 'S',     # Shepherd / Grazier
    Goods.cloth: 'T',    # Weaver / Textilist
    Goods.none: '-',
}


from enum import Enum, auto

class Goods(Enum):
    food = auto()
    wood = auto()
    furn = auto()
    gov = auto()
    none = auto()


# Profession display characters (one per Goods value)
profession = {
    Goods.food: 'F',
    Goods.wood: 'W',
    Goods.furn: 'C',
    Goods.gov: 'G',
    Goods.none: '-',
}


"""Commodity-list compatibility with exact thousandth-unit food balances.

Only the stored representation of edible goods changes. Every public read,
iteration, slice, pickle, and copy exposes ordinary commodity units.
"""
from decimal import Decimal, ROUND_HALF_EVEN
from goods import Goods

SCALE = 1000
EDIBLE = frozenset((int(Goods.food), int(Goods.prepared_food)))


def milli(value):
    return int((Decimal(str(value)) * SCALE).quantize(Decimal('1'), rounding=ROUND_HALF_EVEN))


def _encode(index, value):
    if index not in EDIBLE:
        return value
    units = milli(value)
    if units < 0:
        raise ValueError('Negative physical food inventory')
    return units


class FoodInventory(list):
    def __init__(self, values=()):
        super().__init__(_encode(i, v) for i, v in enumerate(values))

    def __getitem__(self, index):
        if isinstance(index, slice):
            return list(self)[index]
        value = super().__getitem__(index)
        i = index if index >= 0 else len(self) + index
        return value / SCALE if i in EDIBLE else value

    def __setitem__(self, index, value):
        if isinstance(index, slice):
            values = list(self)
            values[index] = value
            encoded = [_encode(i, v) for i, v in enumerate(values)]
            list.clear(self)
            list.extend(self, encoded)
        else:
            i = index if index >= 0 else len(self) + index
            list.__setitem__(self, index, _encode(i, value))

    def __iter__(self):
        return (self[i] for i in range(len(self)))

    def __repr__(self):
        return repr(list(self))

    def __eq__(self, other):
        return list(self) == list(other) if isinstance(other, (list, tuple)) else False

    def __ne__(self, other):
        return not self == other

    def copy(self):
        return type(self)(list(self))

    def extend(self, values):
        for value in values:
            self.append(value)

    def append(self, value):
        list.append(self, _encode(len(self), value))

    def __reduce_ex__(self, protocol):
        return type(self), (list(self),)

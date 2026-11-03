"""Located institutional grain. The aggregate property is a read-only sum."""
from food_inventory import milli


class FoodStore:
    @property
    def food_inventory(self):
        book = self.__dict__.get('food_by_site_milli')
        return sum(book.values()) / 1000 if book is not None else self.__dict__.get('food_inventory', 0)

    @food_inventory.setter
    def food_inventory(self, value):
        # Initialization/legacy administrative endowments have one declared
        # default location. Ordinary transfers always call add_food(site,...).
        book = self.__dict__.setdefault('food_by_site_milli', {})
        site = self.__dict__.get('food_default_site', '__unassigned__')
        other = sum(amount for name, amount in book.items() if name != site)
        amount = milli(value) - other
        if amount < 0:
            raise ValueError('Cannot remove food held at another physical site')
        book[site] = amount

    def bind_food_site(self, region):
        if 'food_by_site_milli' not in self.__dict__:
            self.food_by_site_milli = {'__unassigned__': milli(self.__dict__.pop('food_inventory', 0))}
        if 'food_default_site' not in self.__dict__:
            self.food_default_site = region.name
            self.food_by_site_milli[region.name] = (self.food_by_site_milli.get(region.name, 0)
                                                  + self.food_by_site_milli.pop('__unassigned__', 0))

    def food_at(self, region=None):
        if region is None:
            return self.food_inventory
        book = self.__dict__.get('food_by_site_milli')
        if book is None:
            return 0.0
        return book.get(region.name, 0) / 1000

    def add_food(self, region, quantity):
        if region is not None:
            self.bind_food_site(region)
        book = self.__dict__.setdefault('food_by_site_milli', {})
        site = region.name if region is not None else self.__dict__.get('food_default_site', '__unassigned__')
        amount = book.get(site, 0) + milli(quantity)
        if amount < 0:
            raise ValueError('Insufficient local institutional food')
        book[site] = amount

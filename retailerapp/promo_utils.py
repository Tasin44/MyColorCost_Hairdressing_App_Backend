from math import floor
from decimal import Decimal

def calculate_promo_price(unit_price, quantity, promo_buy_qty, promo_free_qty):
    """
    Calculate total price after Buy X Get Y Free promo.

    Example: Buy 5 Get 1 Free, customer orders 12
      set_size     = 5 + 1 = 6
      complete_sets = floor(12 / 6) = 2
      free_items   = 2 * 1 = 2
      paid_items   = 12 - 2 = 10
      total        = 10 * unit_price
    """
    set_size = promo_buy_qty + promo_free_qty
    complete_sets = floor(quantity / set_size)
    free_items = complete_sets * promo_free_qty
    paid_items = quantity - free_items
    return Decimal(str(unit_price)) * paid_items
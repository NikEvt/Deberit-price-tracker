from decimal import Decimal

PRICE_PRECISION = 20
PRICE_SCALE = 8

_QUANTUM = Decimal(1).scaleb(-PRICE_SCALE)


def quantize_price(value: Decimal) -> Decimal:
    return value.quantize(_QUANTUM)

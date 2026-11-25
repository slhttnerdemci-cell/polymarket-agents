import math

from core.fees import round_trip_cost


def floor_to_tick(price: float, tick: float) -> float | None:
    if tick <= 0 or price <= 0:
        return None
    steps = math.floor((price + 1e-12) / tick)
    floored = round(steps * tick, 6)
    if floored <= 0 or floored >= 1:
        return None
    return floored


def calculate_limit_price(exit_estimate: float, ask: float, fee_rate: float, buffer: float, tick: float) -> float | None:
    """ℓ_max = v - c - ε, floored to the market tick."""
    if ask <= 0 or exit_estimate <= 0:
        return None
    cost = round_trip_cost(ask, exit_estimate, fee_rate)
    raw = exit_estimate - cost - buffer
    return floor_to_tick(raw, tick)

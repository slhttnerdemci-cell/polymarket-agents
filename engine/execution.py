from dataclasses import dataclass

from core.fees import fee_usdc
from core.orderbook import BookSnapshot, Level


@dataclass(frozen=True)
class Fill:
    shares: float
    usdc: float
    avg_price: float
    fee_usdc: float

    @property
    def filled(self) -> bool:
        return self.shares > 0


def walk_buy(book: BookSnapshot, shares: float, limit: float, fee_rate: float) -> Fill:
    """Buy IOC: lift asks at or below the limit. Unfilled size is cancelled."""
    return _walk(book.asks, shares, fee_rate, rising=True, limit=limit)


def walk_sell(book: BookSnapshot, shares: float, fee_rate: float, min_price: float = 0.0) -> Fill:
    """Sell IOC: hit bids at or above min_price."""
    return _walk(book.bids, shares, fee_rate, rising=False, limit=min_price)


def mark_sell(book: BookSnapshot, shares: float, fee_rate: float) -> Fill:
    """What a sell would receive on this snapshot. Does not change a portfolio."""
    return walk_sell(book, shares, fee_rate, min_price=0.0)


def _walk(levels: list[Level], shares: float, fee_rate: float, rising: bool, limit: float) -> Fill:
    remaining = shares
    filled = 0.0
    usdc = 0.0
    fee = 0.0
    for level in levels:
        if remaining <= 1e-12:
            break
        if rising and level.price > limit + 1e-12:
            break
        if not rising and level.price < limit - 1e-12:
            break
        take = min(remaining, level.size)
        usdc += take * level.price
        fee += fee_usdc(take, level.price, fee_rate)
        filled += take
        remaining -= take
    if filled <= 0:
        return Fill(shares=0.0, usdc=0.0, avg_price=0.0, fee_usdc=0.0)
    return Fill(shares=filled, usdc=usdc, avg_price=usdc / filled, fee_usdc=fee)

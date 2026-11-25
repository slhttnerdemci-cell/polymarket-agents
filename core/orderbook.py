import json
from dataclasses import dataclass, field

import aiohttp


@dataclass(frozen=True)
class Level:
    price: float
    size: float


@dataclass
class BookSnapshot:
    token_id: str
    bids: list[Level] = field(default_factory=list)
    asks: list[Level] = field(default_factory=list)
    ok: bool = False

    @property
    def best_bid(self) -> float:
        return self.bids[0].price if self.bids else 0.0

    @property
    def best_ask(self) -> float:
        return self.asks[0].price if self.asks else 0.0

    def empty(self) -> bool:
        return not self.bids and not self.asks

    def tradable(self) -> bool:
        return self.ok and bool(self.bids) and bool(self.asks)

    def depth(self, side: str, levels: int) -> float:
        rows = self.bids if side == "bid" else self.asks
        return sum(level.size for level in rows[:levels])

    def ask_depth_to(self, limit: float) -> float:
        return sum(level.size for level in self.asks if level.price <= limit + 1e-12)


def snapshot_from_payload(token_id: str, data: dict) -> BookSnapshot:
    bids = _levels(data.get("bids"))
    asks = _levels(data.get("asks"))
    bids.sort(key=lambda level: level.price, reverse=True)
    asks.sort(key=lambda level: level.price)
    return BookSnapshot(token_id=token_id, bids=bids, asks=asks, ok=True)


def _levels(rows) -> list[Level]:
    parsed: list[Level] = []
    for row in rows or []:
        try:
            price = float(row["price"])
            size = float(row["size"])
        except (KeyError, TypeError, ValueError):
            continue
        if size > 0 and 0 < price < 1:
            parsed.append(Level(price=price, size=size))
    return parsed


async def fetch_book(session: aiohttp.ClientSession, token_id: str) -> BookSnapshot:
    url = f"https://clob.polymarket.com/book?token_id={token_id}"
    try:
        async with session.get(url) as resp:
            if resp.status != 200:
                return BookSnapshot(token_id=token_id, ok=False)
            data = await resp.json()
            return snapshot_from_payload(token_id, data)
    except (aiohttp.ClientError, TimeoutError, json.JSONDecodeError):
        return BookSnapshot(token_id=token_id, ok=False)

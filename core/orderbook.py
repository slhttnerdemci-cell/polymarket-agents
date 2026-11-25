import aiohttp
from typing import Dict, List

class OrderBook:
    def __init__(self, token_id: str):
        self.token_id = token_id
        self.bids: List[Dict] = []
        self.asks: List[Dict] = []
        self.best_bid = 0.0
        self.best_ask = 0.0

    async def fetch(self) -> bool:
        url = f"https://clob.polymarket.com/book?token_id={self.token_id}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5) as resp:
                    if resp.status != 200:
                        return False
                    data = await resp.json()
                    self.bids = data.get("bids", [])
                    self.asks = data.get("asks", [])
                    if self.bids:
                        self.best_bid = float(self.bids[0]["price"])
                    if self.asks:
                        self.best_ask = float(self.asks[0]["price"])
                    return True
        except Exception:
            return False

    def get_depth(self, side: str, levels: int) -> float:
        levels_list = self.bids if side == "bid" else self.asks
        total = 0.0
        for level in levels_list[:levels]:
            total += float(level.get("size", 0))
        return total

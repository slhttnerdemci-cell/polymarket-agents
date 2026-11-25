import asyncio
import time
from core.orderbook import OrderBook
from core import config
from agents import pulse, impact, edge, size, entry, exit

class VirtualPortfolio:
    def __init__(self, initial: float):
        self.cash = initial
        self.position = 0.0
        self.entry_price = 0.0
        self.entry_time = 0.0
        self.entry_imbalance = 0.0
        self.trades = []

    def open_position(self, price: float, size_usdc: float, imbalance: float):
        shares = size_usdc / price
        self.cash -= size_usdc
        self.position = shares
        self.entry_price = price
        self.entry_time = time.time()
        self.entry_imbalance = imbalance
        self.trades.append({"side": "BUY", "price": price, "size": size_usdc, "time": time.time()})

    def close_position(self, price: float):
        proceeds = self.position * price
        pnl = proceeds - (self.position * self.entry_price)
        self.cash += proceeds
        self.trades.append({"side": "SELL", "price": price, "pnl": pnl, "time": time.time()})
        self.position = 0.0
        return pnl

async def run_simulation(token_id: str, duration_minutes: int = 30):
    ob = OrderBook(token_id)
    portfolio = VirtualPortfolio(config.VIRTUAL_BANKROLL)
    end_time = time.time() + duration_minutes * 60

    print(f"Starting paper trading on {token_id}")
    while time.time() < end_time:
        success = await ob.fetch()
        if not success:
            await asyncio.sleep(config.POLL_INTERVAL)
            continue

        i = pulse.calculate_imbalance(ob)
        v = impact.calculate_impact(ob.best_bid, i)
        e = edge.calculate_edge(v, ob.best_ask)

        if portfolio.position == 0 and e > config.MIN_EDGE:
            sz = size.calculate_size(e, portfolio.cash)
            if sz > 0:
                limit = entry.calculate_limit_price(v)
                portfolio.open_position(limit, sz, i)
                print(f"OPEN @ {limit:.4f} | edge={e:.4f}")

        elif portfolio.position > 0:
            if exit.should_exit(portfolio.entry_time, i, portfolio.entry_imbalance):
                pnl = portfolio.close_position(ob.best_bid)
                print(f"CLOSE | PnL={pnl:.2f}")

        await asyncio.sleep(config.POLL_INTERVAL)

    print(f"Final cash: {portfolio.cash:.2f}")
    return portfolio

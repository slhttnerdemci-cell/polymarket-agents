import tempfile
import unittest
from pathlib import Path

from agents.edge import calculate_edge
from agents.entry import calculate_limit_price
from agents.impact import append_sample, fit_coefficients, frozen_coefficients
from agents.pulse import calculate_imbalance
from core.fees import fee_per_share, fee_usdc
from core.markets import parse_event
from core.orderbook import BookSnapshot, Level, snapshot_from_payload
from core.params import Params
from engine.execution import walk_buy, walk_sell
from engine.orchestrator import decide
from engine.portfolio import Portfolio


def params(**overrides) -> Params:
    values = dict(
        alpha=0.0,
        beta=0.15,
        min_edge=0.012,
        buffer=0.005,
        fee_rate=0.05,
        adverse_move=0.05,
        risk_fraction=0.02,
        max_position_usdc=50.0,
        max_hold_seconds=45.0,
        entry_cutoff_seconds=20.0,
        force_flatten_seconds=8.0,
        pressure_reverse_threshold=0.35,
        imbalance_depth=5,
        bankroll=1000.0,
        poll_interval=2.0,
        tick_size=0.01,
        min_shares=5.0,
        asset="btc",
        window_seconds=300,
        use_archive=True,
        min_fit_samples=8,
    )
    values.update(overrides)
    return Params(**values)


def book(token: str, bids: list[tuple[float, float]], asks: list[tuple[float, float]], ok: bool = True) -> BookSnapshot:
    return BookSnapshot(
        token_id=token,
        bids=[Level(price, size) for price, size in bids],
        asks=[Level(price, size) for price, size in asks],
        ok=ok,
    )


def strong_up() -> BookSnapshot:
    return book("up-token", [(0.46, 200)], [(0.48, 30)])


def quiet() -> BookSnapshot:
    return book("down-token", [(0.40, 10)], [(0.48, 10)])


class FeeTests(unittest.TestCase):
    def test_doc_examples(self):
        self.assertEqual(fee_usdc(100, 0.50, 0.05), 1.25)
        self.assertEqual(fee_usdc(100, 0.10, 0.05), 0.45)

    def test_fee_peaks_at_half(self):
        self.assertGreater(fee_per_share(0.50, 0.05), fee_per_share(0.10, 0.05))


class BookTests(unittest.TestCase):
    def test_sorts_levels(self):
        snap = snapshot_from_payload(
            "t",
            {"bids": [{"price": "0.40", "size": "5"}, {"price": "0.46", "size": "2"}], "asks": [{"price": "0.55", "size": "3"}, {"price": "0.50", "size": "4"}]},
        )
        self.assertEqual(snap.best_bid, 0.46)
        self.assertEqual(snap.best_ask, 0.50)

    def test_empty_book_has_no_imbalance(self):
        empty = book("t", [], [])
        self.assertIsNone(calculate_imbalance(empty, 5))


class FillTests(unittest.TestCase):
    def test_buy_walks_only_to_the_limit(self):
        snap = book("t", [(0.40, 10)], [(0.40, 5), (0.50, 5), (0.70, 20)])
        fill = walk_buy(snap, 30, 0.50, 0.05)
        self.assertEqual(fill.shares, 10)
        self.assertAlmostEqual(fill.usdc, 4.5)
        self.assertAlmostEqual(fill.avg_price, 0.45)
        self.assertAlmostEqual(fill.fee_usdc, 0.06 + 0.0625)

    def test_limit_below_ask_does_not_fill(self):
        snap = book("t", [(0.40, 10)], [(0.55, 10)])
        fill = walk_buy(snap, 10, 0.50, 0.05)
        self.assertFalse(fill.filled)

    def test_sell_walks_bids(self):
        snap = book("t", [(0.48, 4), (0.46, 10)], [(0.55, 10)])
        fill = walk_sell(snap, 6, 0.05)
        self.assertEqual(fill.shares, 6)
        self.assertAlmostEqual(fill.usdc, 4 * 0.48 + 2 * 0.46)


class DecisionTests(unittest.TestCase):
    def test_weak_edge_waits(self):
        decision = decide(quiet(), quiet(), None, now=1_000, expiry=2_000, params=params(), alpha=0.0, beta=0.0, cash=1000)
        self.assertEqual(decision.action, "wait")
        self.assertEqual(decision.reason, "kenar yetmedi")

    def test_buy_uses_the_better_side(self):
        decision = decide(strong_up(), quiet(), None, now=1_000, expiry=2_000, params=params(), alpha=0.0, beta=0.15, cash=1000)
        self.assertEqual(decision.action, "buy")
        self.assertEqual(decision.outcome, "up")
        self.assertEqual(decision.token_id, "up-token")
        self.assertGreater(decision.limit_price, 0.47)
        self.assertLessEqual(decision.shares, 40)

    def test_open_position_blocks_the_other_side(self):
        portfolio = Portfolio(cash=1000)
        portfolio.apply_buy("up", "up-token", 10, 4.7, 0.47, 0.05, 0.8, 0.45, 900, "w", 20)
        decision = decide(
            strong_up(),
            strong_up(),
            portfolio.position,
            now=910,
            expiry=2_000,
            params=params(),
            alpha=0.0,
            beta=0.15,
            cash=portfolio.cash,
        )
        self.assertNotEqual(decision.action, "buy")

    def test_pressure_reversal_sells(self):
        portfolio = Portfolio(cash=1000)
        portfolio.apply_buy("up", "up-token", 10, 4.5, 0.45, 0.02, 0.8, 0.45, 900, "w", 20)
        faded = book("up-token", [(0.44, 12), (0.43, 10)], [(0.46, 40)])
        decision = decide(faded, quiet(), portfolio.position, now=910, expiry=2_000, params=params(), alpha=0.0, beta=0.15, cash=portfolio.cash)
        self.assertEqual(decision.action, "sell")
        self.assertEqual(decision.reason, "baski dondu")

    def test_stronger_pressure_holds(self):
        portfolio = Portfolio(cash=1000)
        portfolio.apply_buy("up", "up-token", 10, 4.5, 0.45, 0.02, 0.5, 0.45, 900, "w", 20)
        hotter = book("up-token", [(0.46, 50)], [(0.48, 5)])
        decision = decide(hotter, quiet(), portfolio.position, now=910, expiry=2_000, params=params(), alpha=0.0, beta=0.15, cash=portfolio.cash)
        self.assertEqual(decision.action, "wait")

    def test_hold_time_sells(self):
        portfolio = Portfolio(cash=1000)
        portfolio.apply_buy("up", "up-token", 10, 4.5, 0.45, 0.02, 0.2, 0.45, 900, "w", 20)
        same = book("up-token", [(0.45, 20)], [(0.47, 20)])
        decision = decide(same, quiet(), portfolio.position, now=960, expiry=2_000, params=params(), alpha=0.0, beta=0.0, cash=portfolio.cash)
        self.assertEqual(decision.action, "sell")
        self.assertEqual(decision.reason, "sure doldu")

    def test_clock_blocks_a_new_entry(self):
        decision = decide(strong_up(), quiet(), None, now=1_990, expiry=2_000, params=params(), alpha=0.0, beta=0.15, cash=1000)
        self.assertEqual(decision.action, "wait")
        self.assertEqual(decision.reason, "saat: yeni giris kapali")

    def test_force_flatten(self):
        portfolio = Portfolio(cash=1000)
        portfolio.apply_buy("up", "up-token", 10, 4.5, 0.45, 0.02, 0.2, 0.45, 1_990, "w", 20)
        same = book("up-token", [(0.45, 20)], [(0.47, 20)])
        decision = decide(same, quiet(), portfolio.position, now=1_995, expiry=2_000, params=params(), alpha=0.0, beta=0.0, cash=portfolio.cash)
        self.assertEqual(decision.action, "sell")
        self.assertEqual(decision.reason, "pencere kapaniyor")


class PortfolioTests(unittest.TestCase):
    def test_realized_pnl_uses_the_fill_and_leaves_the_rest_open(self):
        portfolio = Portfolio(cash=100)
        portfolio.apply_buy("up", "t", 10, 4.5, 0.45, 0.10, 0.4, 0.44, 1, "w", 20)
        self.assertEqual(portfolio.realized_pnl, 0.0)
        self.assertAlmostEqual(portfolio.cash, 100 - 4.5 - 0.10)
        trade = portfolio.apply_sell(4, 1.92, 0.48, 0.04, 2, "baski dondu")
        self.assertIsNotNone(trade)
        expected = 4 * (0.48 - 0.45) - 0.04 - 0.04
        self.assertAlmostEqual(trade.pnl, expected)
        self.assertAlmostEqual(portfolio.realized_pnl, expected)
        self.assertIsNotNone(portfolio.position)
        self.assertAlmostEqual(portfolio.position.shares, 6)

    def test_limit_formula_floors_to_tick(self):
        limit = calculate_limit_price(0.55, 0.47, 0.05, 0.005, 0.01)
        self.assertIsNotNone(limit)
        self.assertLessEqual(limit, 0.55)
        edge = calculate_edge(0.55, 0.47, 0.05)
        self.assertGreater(edge, 0.017)


class ArchiveTests(unittest.TestCase):
    def test_fit_ignores_the_current_window(self):
        past = []
        for imbalance, delta in ((0.0, 0.01), (0.2, 0.02), (0.4, 0.03), (0.6, 0.04), (0.8, 0.05), (1.0, 0.06), (-0.2, 0.0), (-0.4, -0.01)):
            past.append({"window_id": "old", "imbalance": imbalance, "entry_bid": 0.40, "exit_price": 0.40 + delta})
        past.append({"window_id": "now", "imbalance": 1.0, "entry_bid": 0.40, "exit_price": 0.90})
        fitted = fit_coefficients(past, "now", 8)
        contaminated = fit_coefficients(past, "other", 8)
        self.assertIsNotNone(fitted)
        self.assertAlmostEqual(fitted[1], 0.05, places=6)
        self.assertNotAlmostEqual(contaminated[1], fitted[1], places=3)

    def test_frozen_coefficients_fall_back_to_the_sliders(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "samples.json"
            append_sample({"window_id": "old", "imbalance": 0.1, "entry_bid": 0.4, "exit_price": 0.41}, path)
            alpha, beta, source, count = frozen_coefficients("now", 0.0, 0.15, True, 8, path)
        self.assertEqual(source, "arayuz")
        self.assertEqual(alpha, 0.0)
        self.assertEqual(beta, 0.15)
        self.assertEqual(count, 1)


class MarketParseTests(unittest.TestCase):
    def test_pairs_up_and_down_tokens(self):
        payload = [{
            "title": "Bitcoin Up or Down",
            "slug": "btc-updown-5m-100",
            "markets": [{
                "question": "Bitcoin Up or Down",
                "outcomes": "[\"Up\", \"Down\"]",
                "clobTokenIds": "[\"111\", \"222\"]",
                "orderPriceMinTickSize": 0.01,
                "orderMinSize": 5,
                "acceptingOrders": True,
                "closed": False,
            }],
        }]
        market = parse_event(payload, "btc", 100, 300)
        self.assertEqual(market.up_token, "111")
        self.assertEqual(market.down_token, "222")
        self.assertEqual(market.end_ts, 400)


if __name__ == "__main__":
    unittest.main()

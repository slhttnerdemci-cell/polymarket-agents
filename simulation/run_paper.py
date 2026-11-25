import asyncio
import time
from dataclasses import asdict, dataclass, field

import aiohttp

from agents.impact import append_sample, frozen_coefficients
from core.params import Params
from core.markets import fetch_market, slug_for, window_start
from core.orderbook import BookSnapshot, fetch_book
from engine.execution import walk_buy, walk_sell
from engine.orchestrator import decide
from engine.portfolio import Portfolio


@dataclass
class Report:
    question: str = ""
    slug: str = ""
    error: str = ""
    cash: float = 0.0
    realized_pnl: float = 0.0
    open_position: dict | None = None
    trades: list = field(default_factory=list)
    counts: dict = field(default_factory=dict)
    alpha: float = 0.0
    beta: float = 0.0
    coefficient_source: str = ""
    archive_samples: int = 0
    log: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _cycle_view(market, decision, portfolio: Portfolio, now: float, counts: dict) -> dict:
    sides = []
    for side in decision.sides:
        sides.append({
            "outcome": side.outcome,
            "imbalance": side.imbalance,
            "edge": side.edge,
            "note": side.note,
            "shares": side.shares,
        })
    open_position = _position_dict(portfolio.position) if portfolio.position is not None else None
    return {
        "question": market.question or market.slug,
        "remaining": max(0.0, market.end_ts - now),
        "action": decision.action,
        "reason": decision.reason,
        "outcome": decision.outcome,
        "cash": portfolio.cash,
        "realized_pnl": portfolio.realized_pnl,
        "open_position": open_position,
        "counts": dict(counts),
        "sides": sides,
    }


def log_line(report: Report, message: str) -> None:
    report.log.append(message)
    try:
        print(message, flush=True)
    except UnicodeEncodeError:
        print(message.encode("ascii", "replace").decode("ascii"), flush=True)


async def run_simulation(params: Params | None = None, archive_path=None, on_cycle=None, max_cycles: int | None = None) -> Report:
    """Run one 5-minute window. Paper fills only. No wallet and no LLM."""
    settings = params or Params.from_config()
    report = Report(cash=settings.bankroll)
    timeout = aiohttp.ClientTimeout(total=8)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        market = await fetch_market(session, settings.asset, window_seconds=settings.window_seconds)
        if market is None:
            start = window_start(time.time(), settings.window_seconds)
            report.error = f"Acik 5 dakikalik piyasa bulunamadi ({slug_for(settings.asset, start)})."
            log_line(report, report.error)
            return report
        report.question = market.question
        report.slug = market.slug
        alpha, beta, source, sample_count = frozen_coefficients(
            market.slug,
            settings.alpha,
            settings.beta,
            settings.use_archive,
            settings.min_fit_samples,
            *(() if archive_path is None else (archive_path,)),
        )
        report.alpha = alpha
        report.beta = beta
        report.coefficient_source = source
        report.archive_samples = sample_count
        tick = market.tick_size or settings.tick_size
        settings = _with_market_rules(settings, tick, market.min_shares)
        portfolio = Portfolio(cash=settings.bankroll)
        counts = {"buy": 0, "sell": 0, "wait": 0, "unfilled": 0}
        deadline = market.end_ts + 10
        flattened_after_end = False
        cycles = 0
        log_line(report, f"Pencere {market.slug} | katsayi {source} a={alpha:.4f} b={beta:.4f}")

        while time.time() < deadline:
            now = time.time()
            up, down = await asyncio.gather(
                fetch_book(session, market.up_token),
                fetch_book(session, market.down_token),
            )
            decision = decide(
                up=up,
                down=down,
                position=portfolio.position,
                now=now,
                expiry=market.end_ts,
                params=settings,
                alpha=alpha,
                beta=beta,
                cash=portfolio.cash,
            )
            counts[decision.action] = counts.get(decision.action, 0) + 1
            if decision.action == "buy":
                _apply_buy(portfolio, decision, up, down, settings, now, market.slug, report)
            elif decision.action == "sell":
                filled = _apply_sell(portfolio, decision, up, down, settings, now, report, archive_path)
                if not filled:
                    counts["unfilled"] += 1
            elif counts["wait"] == 1 or counts["wait"] % 15 == 0:
                log_line(report, f"bekle | {decision.reason}")

            if on_cycle is not None:
                on_cycle(_cycle_view(market, decision, portfolio, now, counts))

            cycles += 1
            if max_cycles is not None and cycles >= max_cycles:
                break
            if now >= market.end_ts and portfolio.position is None:
                break
            if now >= market.end_ts and portfolio.position is not None:
                if flattened_after_end:
                    break
                flattened_after_end = True
            await asyncio.sleep(max(settings.poll_interval, 0.5))

        report.cash = portfolio.cash
        report.realized_pnl = portfolio.realized_pnl
        report.counts = counts
        report.trades = [_trade_dict(trade) for trade in portfolio.closed]
        if portfolio.position is not None:
            report.open_position = _position_dict(portfolio.position)
        log_line(
            report,
            f"Bitti | nakit {report.cash:.2f} | kapanan PnL {report.realized_pnl:.2f} | "
            f"acik {'var' if report.open_position else 'yok'}",
        )
        return report


def _with_market_rules(settings: Params, tick: float, min_shares: float) -> Params:
    return Params(
        alpha=settings.alpha,
        beta=settings.beta,
        min_edge=settings.min_edge,
        buffer=settings.buffer,
        fee_rate=settings.fee_rate,
        adverse_move=settings.adverse_move,
        risk_fraction=settings.risk_fraction,
        max_position_usdc=settings.max_position_usdc,
        max_hold_seconds=settings.max_hold_seconds,
        entry_cutoff_seconds=settings.entry_cutoff_seconds,
        force_flatten_seconds=settings.force_flatten_seconds,
        pressure_reverse_threshold=settings.pressure_reverse_threshold,
        imbalance_depth=settings.imbalance_depth,
        bankroll=settings.bankroll,
        poll_interval=settings.poll_interval,
        tick_size=tick,
        min_shares=max(settings.min_shares, min_shares),
        asset=settings.asset,
        window_seconds=settings.window_seconds,
        use_archive=settings.use_archive,
        min_fit_samples=settings.min_fit_samples,
    )


def _book_for(decision, up: BookSnapshot, down: BookSnapshot) -> BookSnapshot:
    if decision.token_id == up.token_id:
        return up
    return down


def _apply_buy(portfolio, decision, up, down, settings, now, window_id, report: Report) -> None:
    book = _book_for(decision, up, down)
    per_share = decision.limit_price + settings.fee_rate * 0.25
    shares = decision.shares
    if per_share > 0:
        shares = min(shares, portfolio.cash / per_share)
    if shares < settings.min_shares:
        log_line(report, "al iptal | nakit yetmedi")
        return
    fill = walk_buy(book, shares, decision.limit_price, settings.fee_rate)
    if not fill.filled:
        log_line(report, "al dolmadi | limit defterin altinda kaldi")
        return
    opened = portfolio.apply_buy(
        outcome=decision.outcome,
        token_id=decision.token_id,
        shares=fill.shares,
        usdc=fill.usdc,
        avg_price=fill.avg_price,
        fee=fill.fee_usdc,
        imbalance=float(decision.imbalance or 0.0),
        entry_bid=decision.entry_bid,
        now=now,
        window_id=window_id,
        risk_budget=settings.risk_budget(),
    )
    if not opened:
        log_line(report, "al iptal | pozisyon acilmadi")
        return
    log_line(
        report,
        f"AL {decision.outcome} {fill.shares:.2f} @ {fill.avg_price:.4f} | ucret {fill.fee_usdc:.4f}",
    )


def _apply_sell(portfolio, decision, up, down, settings, now, report: Report, archive_path) -> bool:
    book = _book_for(decision, up, down)
    position = portfolio.position
    if position is None:
        return False
    fill = walk_sell(book, position.shares, settings.fee_rate)
    if not fill.filled:
        log_line(report, f"sat dolmadi | {decision.reason}")
        return False
    trade = portfolio.apply_sell(
        shares=fill.shares,
        usdc=fill.usdc,
        avg_price=fill.avg_price,
        fee=fill.fee_usdc,
        now=now,
        reason=decision.reason,
    )
    if trade is None:
        return False
    sample = {
        "window_id": trade.window_id,
        "imbalance": trade.entry_imbalance,
        "entry_bid": trade.entry_bid,
        "exit_price": trade.exit_price,
        "shares": trade.shares,
        "pnl": trade.pnl,
    }
    if archive_path is None:
        append_sample(sample)
    else:
        append_sample(sample, archive_path)
    log_line(
        report,
        f"SAT {trade.outcome} {trade.shares:.2f} @ {trade.exit_price:.4f} | "
        f"PnL {trade.pnl:.4f} | {trade.reason}",
    )
    return True


def _trade_dict(trade) -> dict:
    return {
        "outcome": trade.outcome,
        "shares": round(trade.shares, 4),
        "entry": round(trade.entry_price, 4),
        "exit": round(trade.exit_price, 4),
        "pnl": round(trade.pnl, 4),
        "reason": trade.reason,
    }


def _position_dict(position) -> dict:
    return {
        "outcome": position.outcome,
        "shares": round(position.shares, 4),
        "entry": round(position.avg_price, 4),
        "exposure_usdc": round(position.exposure_usdc, 4),
    }


def main() -> None:
    report = asyncio.run(run_simulation())
    if report.error:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

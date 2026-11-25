from dataclasses import dataclass, field

from agents.edge import calculate_edge
from agents.entry import calculate_limit_price
from agents.exit import exit_reason
from agents.impact import estimate_exit
from agents.pulse import calculate_imbalance
from agents.size import calculate_size
from core.orderbook import BookSnapshot
from core.params import Params
from engine.execution import mark_sell
from engine.portfolio import Position


@dataclass
class SideView:
    outcome: str
    imbalance: float | None = None
    exit_estimate: float | None = None
    edge: float | None = None
    limit_price: float | None = None
    depth: float | None = None
    shares: float | None = None
    note: str = ""


@dataclass
class Decision:
    action: str
    reason: str
    outcome: str | None = None
    token_id: str | None = None
    shares: float = 0.0
    limit_price: float = 0.0
    imbalance: float | None = None
    entry_bid: float = 0.0
    sides: list[SideView] = field(default_factory=list)


def decide(
    up: BookSnapshot,
    down: BookSnapshot,
    position: Position | None,
    now: float,
    expiry: float,
    params: Params,
    alpha: float,
    beta: float,
    cash: float,
) -> Decision:
    """One snapshot in, one order instruction out. No second strategy."""
    books = {"up": up, "down": down}
    if position is not None:
        book = up if position.token_id == up.token_id else down
        return _exit_decision(book, position, now, expiry, params)

    if expiry - now <= params.entry_cutoff_seconds:
        return Decision(action="wait", reason="saat: yeni giris kapali")

    views: list[SideView] = []
    best: tuple[float, SideView, BookSnapshot] | None = None
    tied = False
    for outcome, book in books.items():
        view, score = _score_entry(outcome, book, params, alpha, beta, cash)
        views.append(view)
        if score is None:
            continue
        if best is None or score > best[0] + 1e-12:
            best = (score, view, book)
            tied = False
        elif abs(score - best[0]) <= 1e-12:
            tied = True

    if best is None or tied:
        reason = "kenar esit" if tied else _wait_reason(views)
        return Decision(action="wait", reason=reason, sides=views)

    _, view, book = best
    return Decision(
        action="buy",
        reason="kenar gecti",
        outcome=view.outcome,
        token_id=book.token_id,
        shares=float(view.shares or 0.0),
        limit_price=float(view.limit_price or 0.0),
        imbalance=view.imbalance,
        entry_bid=book.best_bid,
        sides=views,
    )


def _exit_decision(
    book: BookSnapshot,
    position: Position,
    now: float,
    expiry: float,
    params: Params,
) -> Decision:
    imbalance = calculate_imbalance(book, params.imbalance_depth) if book.ok else None
    quote = mark_sell(book, position.shares, params.fee_rate) if book.ok else None
    mark_loss = 0.0
    if quote is not None and quote.filled:
        sold = min(quote.shares, position.shares)
        entry_fee = position.entry_fee * (sold / position.shares)
        mark_pnl = sold * (quote.avg_price - position.avg_price) - entry_fee - quote.fee_usdc
        mark_loss = max(0.0, -mark_pnl)
    reason = exit_reason(
        now=now,
        expiry=expiry,
        entry_time=position.entry_time,
        entry_imbalance=position.entry_imbalance,
        current_imbalance=imbalance,
        mark_loss=mark_loss,
        risk_budget=position.risk_budget,
        max_hold_seconds=params.max_hold_seconds,
        force_flatten_seconds=params.force_flatten_seconds,
        reverse_threshold=params.pressure_reverse_threshold,
    )
    if reason is None:
        return Decision(action="wait", reason="tut", outcome=position.outcome, token_id=position.token_id)
    return Decision(
        action="sell",
        reason=reason,
        outcome=position.outcome,
        token_id=position.token_id,
        shares=position.shares,
        limit_price=0.0,
        imbalance=imbalance,
    )


def _score_entry(
    outcome: str,
    book: BookSnapshot,
    params: Params,
    alpha: float,
    beta: float,
    cash: float,
) -> tuple[SideView, float | None]:
    view = SideView(outcome=outcome)
    if not book.tradable():
        view.note = "bos defter"
        return view, None
    imbalance = calculate_imbalance(book, params.imbalance_depth)
    if imbalance is None:
        view.note = "bos defter"
        return view, None
    exit_estimate = estimate_exit(book.best_bid, imbalance, alpha, beta)
    edge = calculate_edge(exit_estimate, book.best_ask, params.fee_rate)
    limit = calculate_limit_price(exit_estimate, book.best_ask, params.fee_rate, params.buffer, params.tick_size)
    view.imbalance = imbalance
    view.exit_estimate = exit_estimate
    view.edge = edge
    view.limit_price = limit
    if edge is None or edge <= params.edge_hurdle:
        view.note = "kenar yetmedi"
        return view, None
    if limit is None or limit < book.best_ask:
        view.note = "limit defterin altinda"
        return view, None
    depth = book.ask_depth_to(limit)
    shares = calculate_size(
        bankroll=params.bankroll,
        cash=cash,
        ask=book.best_ask,
        depth_shares=depth,
        risk_fraction=params.risk_fraction,
        adverse_move=params.adverse_move,
        max_position_usdc=params.max_position_usdc,
        open_exposure_usdc=0.0,
        min_shares=params.min_shares,
    )
    view.depth = depth
    view.shares = shares
    if shares <= 0:
        view.note = "miktar yetmedi"
        return view, None
    view.note = "aday"
    return view, edge


def _wait_reason(views: list[SideView]) -> str:
    notes = [view.note for view in views if view.note and view.note != "aday"]
    if not notes:
        return "kenar esit"
    if len(set(notes)) == 1:
        return notes[0]
    return notes[0]

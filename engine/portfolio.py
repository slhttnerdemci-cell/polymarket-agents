from dataclasses import dataclass, field


@dataclass
class Position:
    outcome: str
    token_id: str
    shares: float
    avg_price: float
    entry_fee: float
    entry_imbalance: float
    entry_bid: float
    entry_time: float
    window_id: str
    risk_budget: float

    @property
    def exposure_usdc(self) -> float:
        return self.shares * self.avg_price


@dataclass
class ClosedTrade:
    outcome: str
    token_id: str
    shares: float
    entry_price: float
    exit_price: float
    pnl: float
    entry_fee: float
    exit_fee: float
    window_id: str
    reason: str
    entry_imbalance: float
    entry_bid: float
    entry_time: float
    exit_time: float


@dataclass
class Portfolio:
    cash: float
    position: Position | None = None
    closed: list[ClosedTrade] = field(default_factory=list)

    @property
    def realized_pnl(self) -> float:
        return sum(trade.pnl for trade in self.closed)

    def apply_buy(
        self,
        outcome: str,
        token_id: str,
        shares: float,
        usdc: float,
        avg_price: float,
        fee: float,
        imbalance: float,
        entry_bid: float,
        now: float,
        window_id: str,
        risk_budget: float,
    ) -> bool:
        if self.position is not None or shares <= 0:
            return False
        spent = usdc + fee
        if spent > self.cash + 1e-9:
            return False
        self.cash -= spent
        self.position = Position(
            outcome=outcome,
            token_id=token_id,
            shares=shares,
            avg_price=avg_price,
            entry_fee=fee,
            entry_imbalance=imbalance,
            entry_bid=entry_bid,
            entry_time=now,
            window_id=window_id,
            risk_budget=risk_budget,
        )
        return True

    def apply_sell(
        self,
        shares: float,
        usdc: float,
        avg_price: float,
        fee: float,
        now: float,
        reason: str,
    ) -> ClosedTrade | None:
        position = self.position
        if position is None or shares <= 0:
            return None
        sold = min(shares, position.shares)
        fraction = sold / position.shares
        entry_fee = position.entry_fee * fraction
        pnl = sold * (avg_price - position.avg_price) - entry_fee - fee
        self.cash += usdc - fee
        trade = ClosedTrade(
            outcome=position.outcome,
            token_id=position.token_id,
            shares=sold,
            entry_price=position.avg_price,
            exit_price=avg_price,
            pnl=pnl,
            entry_fee=entry_fee,
            exit_fee=fee,
            window_id=position.window_id,
            reason=reason,
            entry_imbalance=position.entry_imbalance,
            entry_bid=position.entry_bid,
            entry_time=position.entry_time,
            exit_time=now,
        )
        self.closed.append(trade)
        remaining = position.shares - sold
        if remaining <= 1e-9:
            self.position = None
        else:
            position.shares = remaining
            position.entry_fee -= entry_fee
        return trade

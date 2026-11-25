from dataclasses import dataclass

from core import config


@dataclass(frozen=True)
class Params:
    alpha: float
    beta: float
    min_edge: float
    buffer: float
    fee_rate: float
    adverse_move: float
    risk_fraction: float
    max_position_usdc: float
    max_hold_seconds: float
    entry_cutoff_seconds: float
    force_flatten_seconds: float
    pressure_reverse_threshold: float
    imbalance_depth: int
    bankroll: float
    poll_interval: float
    tick_size: float
    min_shares: float
    asset: str
    window_seconds: int
    use_archive: bool
    min_fit_samples: int

    @classmethod
    def from_config(cls) -> "Params":
        return cls(
            alpha=float(config.ALPHA),
            beta=float(config.BETA),
            min_edge=float(config.MIN_EDGE),
            buffer=float(config.BUFFER),
            fee_rate=float(config.FEE_RATE),
            adverse_move=float(config.ADVERSE_MOVE),
            risk_fraction=float(config.RISK_FRACTION),
            max_position_usdc=float(config.MAX_POSITION_USDC),
            max_hold_seconds=float(config.MAX_HOLD_SECONDS),
            entry_cutoff_seconds=float(config.ENTRY_CUTOFF_SECONDS),
            force_flatten_seconds=float(config.FORCE_FLATTEN_SECONDS),
            pressure_reverse_threshold=float(config.PRESSURE_REVERSE_THRESHOLD),
            imbalance_depth=int(config.IMBALANCE_DEPTH),
            bankroll=float(config.VIRTUAL_BANKROLL),
            poll_interval=float(config.POLL_INTERVAL),
            tick_size=float(config.TICK_SIZE),
            min_shares=float(config.MIN_SHARES),
            asset=str(config.ASSET),
            window_seconds=int(config.WINDOW_SECONDS),
            use_archive=bool(config.USE_ARCHIVE),
            min_fit_samples=int(config.MIN_FIT_SAMPLES),
        )

    @property
    def edge_hurdle(self) -> float:
        return self.min_edge + self.buffer

    def risk_budget(self) -> float:
        return self.bankroll * self.risk_fraction

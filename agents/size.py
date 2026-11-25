def calculate_size(
    bankroll: float,
    cash: float,
    ask: float,
    depth_shares: float,
    risk_fraction: float,
    adverse_move: float,
    max_position_usdc: float,
    open_exposure_usdc: float,
    min_shares: float,
) -> float:
    """Q = min(B/L, depth, position cap, cash). Shares, not USDC."""
    if ask <= 0 or adverse_move <= 0 or cash <= 0 or depth_shares <= 0:
        return 0.0
    risk_budget = bankroll * risk_fraction
    by_risk = risk_budget / adverse_move
    room_usdc = max(0.0, max_position_usdc - open_exposure_usdc)
    by_cap = room_usdc / ask
    by_cash = cash / ask
    shares = min(by_risk, depth_shares, by_cap, by_cash)
    if shares < min_shares:
        return 0.0
    return shares

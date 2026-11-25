def fee_per_share(price: float, fee_rate: float) -> float:
    """USDC fee for one share. Peaks at price 0.50."""
    if fee_rate <= 0 or price <= 0 or price >= 1:
        return 0.0
    return fee_rate * price * (1.0 - price)


def fee_usdc(shares: float, price: float, fee_rate: float) -> float:
    """fee = shares × feeRate × price × (1 − price), rounded to 0.00001 USDC."""
    if shares <= 0 or fee_rate <= 0 or price <= 0 or price >= 1:
        return 0.0
    raw = shares * fee_rate * price * (1.0 - price)
    rounded = round(raw + 1e-12, 5)
    if rounded < 0.00001:
        return 0.0
    return rounded


def round_trip_cost(entry_price: float, exit_price: float, fee_rate: float) -> float:
    """Per-share cost used by EDGE. Both legs pay the taker fee."""
    return fee_per_share(entry_price, fee_rate) + fee_per_share(exit_price, fee_rate)

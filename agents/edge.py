from core.fees import round_trip_cost


def calculate_edge(exit_estimate: float, ask: float, fee_rate: float) -> float | None:
    """e = v - a - c. c is the taker fee on both legs."""
    if ask <= 0 or ask >= 1 or exit_estimate <= 0:
        return None
    cost = round_trip_cost(ask, exit_estimate, fee_rate)
    return exit_estimate - ask - cost

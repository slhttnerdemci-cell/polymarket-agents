from core import config

def calculate_edge(v: float, best_ask: float) -> float:
    return v - best_ask - config.ROUND_TRIP_COST

from core import config

def calculate_impact(best_bid: float, imbalance: float) -> float:
    return best_bid + config.ALPHA + config.BETA * imbalance

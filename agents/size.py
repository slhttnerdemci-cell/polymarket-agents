from core import config

def calculate_size(edge: float, bankroll: float) -> float:
    if edge <= 0:
        return 0.0
    size = min(config.MAX_POSITION_USDC, bankroll * 0.05)
    return round(size, 2)

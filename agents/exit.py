import time
from core import config

def should_exit(entry_time: float, current_imbalance: float, entry_imbalance: float) -> bool:
    elapsed = time.time() - entry_time
    if elapsed > config.MAX_HOLD_SECONDS:
        return True
    if abs(current_imbalance - entry_imbalance) > config.PRESSURE_REVERSE_THRESHOLD:
        return True
    return False

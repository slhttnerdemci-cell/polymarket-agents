def exit_reason(
    now: float,
    expiry: float,
    entry_time: float,
    entry_imbalance: float,
    current_imbalance: float | None,
    mark_loss: float,
    risk_budget: float,
    max_hold_seconds: float,
    force_flatten_seconds: float,
    reverse_threshold: float,
) -> str | None:
    """Return why a long must close, or None to keep it."""
    if expiry - now <= force_flatten_seconds:
        return "pencere kapaniyor"
    if now - entry_time >= max_hold_seconds:
        return "sure doldu"
    if mark_loss >= risk_budget:
        return "risk"
    if (
        current_imbalance is not None
        and current_imbalance < entry_imbalance - reverse_threshold
    ):
        return "baski dondu"
    return None

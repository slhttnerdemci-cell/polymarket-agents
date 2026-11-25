import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_PATH = ROOT / "data" / "impact_samples.json"


def estimate_exit(best_bid: float, imbalance: float, alpha: float, beta: float) -> float:
    """v = b + α + βI, clamped to a contract price."""
    raw = best_bid + alpha + beta * imbalance
    if raw < 0:
        return 0.0
    if raw > 1:
        return 1.0
    return raw


def fit_coefficients(samples: list[dict], exclude_window: str, min_samples: int) -> tuple[float, float] | None:
    """Least squares of (exit - entry bid) on I, using other windows only."""
    rows = [row for row in samples if str(row.get("window_id")) != str(exclude_window)]
    if len(rows) < min_samples:
        return None
    xs = [float(row["imbalance"]) for row in rows]
    ys = [float(row["exit_price"]) - float(row["entry_bid"]) for row in rows]
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    var_x = sum((x - mean_x) ** 2 for x in xs)
    if var_x < 1e-12:
        return None
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    beta = cov / var_x
    alpha = mean_y - beta * mean_x
    return alpha, beta


def load_samples(path: Path = ARCHIVE_PATH) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def append_sample(sample: dict, path: Path = ARCHIVE_PATH) -> None:
    rows = load_samples(path)
    rows.append(sample)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2), encoding="utf-8")


def frozen_coefficients(
    window_id: str,
    alpha: float,
    beta: float,
    use_archive: bool,
    min_samples: int,
    path: Path = ARCHIVE_PATH,
) -> tuple[float, float, str, int]:
    if not use_archive:
        return alpha, beta, "arayuz", 0
    rows = load_samples(path)
    usable = [row for row in rows if str(row.get("window_id")) != str(window_id)]
    fitted = fit_coefficients(rows, window_id, min_samples)
    if fitted is None:
        return alpha, beta, "arayuz", len(usable)
    return fitted[0], fitted[1], "arsiv", len(usable)

import time

ORDER = ("PULSE", "IMPACT", "EDGE", "SIZE", "ENTRY", "EXIT")

# Stages that actually ran before this reason stopped the cycle.
_RAN_BEFORE = {
    "bos defter": (),
    "kenar yetmedi": ("PULSE", "IMPACT"),
    "kenar esit": ("PULSE", "IMPACT"),
    "limit defterin altinda": ("PULSE", "IMPACT", "EDGE"),
    "miktar yetmedi": ("PULSE", "IMPACT", "EDGE"),
    "saat: yeni giris kapali": (),
}
_STOP_AT = {
    "bos defter": "PULSE",
    "kenar yetmedi": "EDGE",
    "kenar esit": "EDGE",
    "limit defterin altinda": "ENTRY",
    "miktar yetmedi": "SIZE",
    "saat: yeni giris kapali": "ENTRY",
}
_EXIT_REASONS = {"tut", "pencere kapaniyor", "sure doldu", "risk", "baski dondu"}


def idle_snap(cash: float, alpha: float, beta: float, hurdle: float, now: float | None = None) -> dict:
    clock = time.time() if now is None else now
    return {
        "question": "Pencere bekleniyor",
        "remaining": None,
        "action": "bekle",
        "reason": "henuz tur yok",
        "outcome": None,
        "cash": cash,
        "realized_pnl": 0.0,
        "equity": cash,
        "exposure": 0.0,
        "open_position": None,
        "counts": {},
        "sides": [],
        "imbalance": None,
        "alpha": alpha,
        "beta": beta,
        "source": "",
        "hurdle": hurdle,
        "now": clock,
        "event": "",
        "limit_price": 0.0,
        "shares": 0.0,
    }


def desk_from_snap(snap: dict) -> dict:
    """Turn one paper cycle into module cards. States come only from that cycle."""
    modules = {name: {"name": name, "state": "bosta", "detail": "—"} for name in ORDER}
    reason = str(snap.get("reason") or "")
    action = str(snap.get("action") or "bekle")
    _write_details(modules, snap)

    if reason == "henuz tur yok":
        modules["EXIT"]["detail"] = "pozisyon yok"
    elif action == "sell" or reason in _EXIT_REASONS:
        _mark_exit(modules, snap, reason)
    elif action == "buy" or reason == "kenar gecti":
        for name in ("PULSE", "IMPACT", "EDGE", "SIZE", "ENTRY"):
            modules[name]["state"] = "gecti"
        if snap.get("open_position"):
            modules["EXIT"]["detail"] = "acik pozisyon kara yazilmaz"
        else:
            modules["EXIT"]["detail"] = "pozisyon yok"
    elif reason in _STOP_AT:
        for name in _RAN_BEFORE[reason]:
            modules[name]["state"] = "gecti"
        stop = _STOP_AT[reason]
        modules[stop]["state"] = "durdu"
        modules[stop]["detail"] = _join(modules[stop]["detail"], reason)
        modules["EXIT"]["detail"] = "pozisyon yok"
    else:
        modules["EXIT"]["detail"] = reason or "pozisyon yok"

    return {"modules": [modules[name] for name in ORDER], "line": _line(snap)}


def _mark_exit(modules: dict, snap: dict, reason: str) -> None:
    if snap.get("imbalance") is not None or _has(snap, "imbalance"):
        modules["PULSE"]["state"] = "gecti"
    for name in ("IMPACT", "EDGE", "SIZE", "ENTRY"):
        modules[name]["detail"] = "cikis yolu"
    if reason == "tut":
        modules["EXIT"]["state"] = "tutuyor"
        modules["EXIT"]["detail"] = "tut"
    else:
        modules["EXIT"]["state"] = "gecti"
        modules["EXIT"]["detail"] = reason


def _write_details(modules: dict, snap: dict) -> None:
    modules["PULSE"]["detail"] = _pairs(snap, "imbalance", "I", "{:.3f}") or (
        f"I={snap['imbalance']:.3f}" if snap.get("imbalance") is not None else "defter bos"
    )
    impact = _pairs(snap, "exit_estimate", "v", "{:.3f}")
    coeff = f"α={snap.get('alpha', 0):.3f} β={snap.get('beta', 0):.3f}"
    source = snap.get("source") or ""
    if source:
        coeff = f"{coeff} {source}"
    modules["IMPACT"]["detail"] = _join(impact, coeff)
    edge = _pairs(snap, "edge", "e", "{:.3f}")
    hurdle = snap.get("hurdle")
    hurdle_text = f"esik {hurdle:.3f}" if isinstance(hurdle, (int, float)) else ""
    modules["EDGE"]["detail"] = _join(edge, hurdle_text)
    modules["SIZE"]["detail"] = _pairs(snap, "shares", "Q", "{:.2f}") or "—"
    modules["ENTRY"]["detail"] = _pairs(snap, "limit_price", "ℓ", "{:.3f}") or "—"
    if snap.get("open_position"):
        position = snap["open_position"]
        modules["EXIT"]["detail"] = f"acik {position.get('outcome')} {position.get('shares')}"
    else:
        modules["EXIT"]["detail"] = "pozisyon yok"


def _pairs(snap: dict, key: str, label: str, fmt: str) -> str:
    parts = []
    for side in snap.get("sides") or []:
        value = side.get(key)
        if value is None:
            continue
        parts.append(f"{side.get('outcome')} {label}=" + fmt.format(value))
    return " · ".join(parts)


def _has(snap: dict, key: str) -> bool:
    return any(side.get(key) is not None for side in snap.get("sides") or [])


def _join(left: str, right: str) -> str:
    left = left if left and left != "—" else ""
    right = right or ""
    if left and right:
        return f"{left} | {right}"
    return left or right or "—"


def _line(snap: dict) -> str:
    clock = time.strftime("%H:%M:%S", time.localtime(float(snap.get("now") or time.time())))
    event = str(snap.get("event") or "").strip()
    if event:
        return f"{clock}  {event}"
    outcome = snap.get("outcome") or ""
    action = snap.get("action") or "bekle"
    reason = snap.get("reason") or ""
    return "  ".join(part for part in (clock, action, outcome, reason) if part)

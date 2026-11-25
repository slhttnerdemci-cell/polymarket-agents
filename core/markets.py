import json
import time
from dataclasses import dataclass

import aiohttp


@dataclass(frozen=True)
class MarketWindow:
    slug: str
    question: str
    asset: str
    up_token: str
    down_token: str
    start_ts: float
    end_ts: float
    tick_size: float
    min_shares: float
    accepting: bool


def window_start(now: float, window_seconds: int) -> int:
    width = max(int(window_seconds), 1)
    return int(now // width) * width


def slug_for(asset: str, start: int) -> str:
    return f"{asset.lower()}-updown-5m-{start}"


def parse_event(payload, asset: str, start: int, window_seconds: int) -> MarketWindow | None:
    events = payload if isinstance(payload, list) else [payload]
    for event in events:
        if not isinstance(event, dict):
            continue
        markets = event.get("markets") or []
        if not markets and event.get("clobTokenIds"):
            markets = [event]
        for market in markets:
            parsed = _parse_market(market, event, asset, start, window_seconds)
            if parsed is not None:
                return parsed
    return None


def _parse_market(market: dict, event: dict, asset: str, start: int, window_seconds: int) -> MarketWindow | None:
    outcomes = _as_list(market.get("outcomes"))
    token_ids = _as_list(market.get("clobTokenIds"))
    if len(outcomes) < 2 or len(token_ids) < 2:
        return None
    up_token = ""
    down_token = ""
    for label, token_id in zip(outcomes, token_ids):
        name = str(label).strip().lower()
        if name in ("up", "yes"):
            up_token = str(token_id)
        elif name in ("down", "no"):
            down_token = str(token_id)
    if not up_token or not down_token:
        return None
    tick = float(market.get("orderPriceMinTickSize") or 0.01)
    min_shares = float(market.get("orderMinSize") or 5)
    question = str(market.get("question") or event.get("title") or "")
    slug = str(market.get("slug") or event.get("slug") or slug_for(asset, start))
    return MarketWindow(
        slug=slug,
        question=question,
        asset=asset.lower(),
        up_token=up_token,
        down_token=down_token,
        start_ts=float(start),
        end_ts=float(start + window_seconds),
        tick_size=tick if tick > 0 else 0.01,
        min_shares=min_shares if min_shares > 0 else 5.0,
        accepting=bool(market.get("acceptingOrders", True)) and not bool(market.get("closed", False)),
    )


def _as_list(value):
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value:
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []
    return []


async def fetch_market(
    session: aiohttp.ClientSession,
    asset: str,
    now: float | None = None,
    window_seconds: int = 300,
) -> MarketWindow | None:
    clock = time.time() if now is None else now
    start = window_start(clock, window_seconds)
    slug = slug_for(asset, start)
    url = "https://gamma-api.polymarket.com/events"
    try:
        async with session.get(url, params={"slug": slug}) as resp:
            if resp.status != 200:
                return None
            payload = await resp.json()
    except (aiohttp.ClientError, TimeoutError, json.JSONDecodeError):
        return None
    return parse_event(payload, asset, start, window_seconds)

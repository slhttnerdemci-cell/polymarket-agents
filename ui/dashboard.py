import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import asyncio

import pandas as pd
import streamlit as st

from core import config
from core.params import Params
from simulation.run_paper import run_simulation
from ui.terminal_view import desk_from_snap, idle_snap


def _fmt(value) -> str:
    if value is None:
        return "—"
    return f"{value:.4f}"


def _remember(snap: dict) -> None:
    desk = desk_from_snap(snap)
    st.session_state.lines.append(desk["line"])
    st.session_state.curve.append(
        {
            "tur": len(st.session_state.curve) + 1,
            "nakit_ve_maliyet": snap["equity"],
            "kapanan_pnl": snap["realized_pnl"],
        }
    )
    st.session_state.snap = snap


def _show_terminal(slot, snap: dict, lines: list, curve: list) -> None:
    desk = desk_from_snap(snap)
    with slot.container():
        st.subheader(snap["question"])
        remaining = snap.get("remaining")
        counts = snap.get("counts") or {}
        one, two, three, four = st.columns(4)
        one.metric("Kalan süre", "—" if remaining is None else f"{remaining:.0f} sn")
        two.metric("Nakit", f"{snap['cash']:.2f}")
        three.metric("Nakit + açık maliyet", f"{snap['equity']:.2f}")
        four.metric("Kapanan PnL", f"{snap['realized_pnl']:.2f}")
        st.caption(
            f"al {counts.get('buy', 0)} / sat {counts.get('sell', 0)} / bekle {counts.get('wait', 0)}"
            " · açık pozisyon kâra yazılmaz · cüzdan yok"
        )
        st.caption("PULSE → IMPACT → EDGE → SIZE → ENTRY → EXIT")
        cards = st.columns(6)
        for column, module in zip(cards, desk["modules"]):
            with column.container(border=True):
                st.caption(module["name"])
                st.write(module["state"])
                st.caption(module["detail"])
        if snap.get("sides"):
            st.dataframe(
                [
                    {
                        "taraf": side["outcome"],
                        "dengesizlik": _fmt(side.get("imbalance")),
                        "cikis": _fmt(side.get("exit_estimate")),
                        "kenar": _fmt(side.get("edge")),
                        "limit": _fmt(side.get("limit_price")),
                        "pay": _fmt(side.get("shares")),
                        "not": side.get("note") or "",
                    }
                    for side in snap["sides"]
                ],
                use_container_width=True,
            )
        if snap.get("open_position"):
            st.info("Açık pozisyon kâra yazılmaz.")
            st.json(snap["open_position"])
        left, right = st.columns(2)
        with left:
            st.write("Karar satırları")
            if lines:
                st.dataframe(pd.DataFrame({"satir": lines[-20:]}), use_container_width=True, hide_index=True)
            else:
                st.write("Henüz tur yok.")
        with right:
            st.write("Bakiye eğrisi")
            if curve:
                st.line_chart(
                    pd.DataFrame(curve),
                    x="tur",
                    y=["nakit_ve_maliyet", "kapanan_pnl"],
                    height=240,
                )
                st.caption("Nakit artı açık maliyet, ve yalnız kapanan PnL.")
            else:
                st.write("Eğri ilk turdan sonra çizilir.")


def _show_report(report) -> None:
    if report.error:
        st.error(report.error)
        return
    st.write(
        f"Katsayı kaynağı: {report.coefficient_source} | α={report.alpha:.4f} | β={report.beta:.4f} | "
        f"eski örnek {report.archive_samples}"
    )
    if report.open_position:
        st.warning("Pencere bitti. Açık pozisyon kâra yazılmadı.")
        st.json(report.open_position)
    elif report.trades:
        st.success("Açık pozisyon yok.")
    st.write("Kapanan işlemler")
    if report.trades:
        st.dataframe(report.trades, use_container_width=True)
    else:
        st.write("Kapanan işlem yok.")
    with st.expander("Günlük"):
        st.code("\n".join(report.log) if report.log else "Kayıt yok.")


st.set_page_config(page_title="Polymarket Agents", layout="wide")
st.title("Polymarket paper masası")
st.caption("Ajanlar sinyal üretir. Emri kod yürütür. Gerçek emir ve cüzdan yok.")

st.sidebar.header("Parametreler")
config.ASSET = st.sidebar.selectbox("Varlık", ["btc", "eth"], index=0 if config.ASSET == "btc" else 1)
config.ALPHA = st.sidebar.slider("Alpha", -0.05, 0.05, float(config.ALPHA), 0.001)
config.BETA = st.sidebar.slider("Beta", -0.20, 0.40, float(config.BETA), 0.01)
config.MIN_EDGE = st.sidebar.slider("Minimum kenar", 0.0, 0.05, float(config.MIN_EDGE), 0.001)
config.BUFFER = st.sidebar.slider("Tampon ε", 0.0, 0.03, float(config.BUFFER), 0.001)
config.FEE_RATE = st.sidebar.slider("Ücret katsayısı", 0.0, 0.10, float(config.FEE_RATE), 0.01)
config.ADVERSE_MOVE = st.sidebar.slider("Kötü hareket L", 0.01, 0.20, float(config.ADVERSE_MOVE), 0.01)
config.RISK_FRACTION = st.sidebar.slider("Risk payı", 0.005, 0.10, float(config.RISK_FRACTION), 0.005)
config.MAX_POSITION_USDC = st.sidebar.slider("Pozisyon tavanı", 10.0, 200.0, float(config.MAX_POSITION_USDC), 5.0)
config.MAX_HOLD_SECONDS = st.sidebar.slider("Tutma süresi (sn)", 15, 120, int(config.MAX_HOLD_SECONDS), 5)
config.PRESSURE_REVERSE_THRESHOLD = st.sidebar.slider(
    "Baskı dönüş eşiği", 0.05, 0.80, float(config.PRESSURE_REVERSE_THRESHOLD), 0.05
)
config.VIRTUAL_BANKROLL = st.sidebar.number_input("Sanal bankroll", 100.0, 10000.0, float(config.VIRTUAL_BANKROLL))
config.POLL_INTERVAL = st.sidebar.slider("Yoklama (sn)", 1.0, 10.0, float(config.POLL_INTERVAL), 1.0)
config.USE_ARCHIVE = st.sidebar.checkbox("Eski pencerelerden α ve β kullan", value=bool(config.USE_ARCHIVE))

st.sidebar.caption("BTC 5 dakikalık ücret katsayısı 0,05. Diğer kripto 0,01. Maliyet fiyata göre hesaplanır.")

if "lines" not in st.session_state:
    st.session_state.lines = []
    st.session_state.curve = []
    st.session_state.snap = None

run_window = st.button("Bu pencereyi çalıştır")
run_once = st.button("Tek tur bak")

if run_window or run_once:
    st.session_state.lines = []
    st.session_state.curve = []
    st.session_state.snap = None

live = st.empty()
shown = st.session_state.snap or idle_snap(
    config.VIRTUAL_BANKROLL,
    config.ALPHA,
    config.BETA,
    config.MIN_EDGE + config.BUFFER,
)
if not (run_window or run_once):
    _show_terminal(live, shown, st.session_state.lines, st.session_state.curve)

if run_window or run_once:
    params = Params.from_config()

    def on_cycle(snap: dict) -> None:
        _remember(snap)
        _show_terminal(live, snap, st.session_state.lines, st.session_state.curve)

    report = asyncio.run(run_simulation(params, on_cycle=on_cycle, max_cycles=1 if run_once else None))
    if st.session_state.snap is None:
        _show_terminal(live, shown, st.session_state.lines, st.session_state.curve)
    else:
        _show_terminal(live, st.session_state.snap, st.session_state.lines, st.session_state.curve)
    _show_report(report)

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import asyncio

import streamlit as st

from core import config
from core.params import Params
from simulation.run_paper import run_simulation

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

if st.button("Bu pencereyi çalıştır"):
    params = Params.from_config()
    with st.spinner("Pencere kapanana kadar paper çalışıyor..."):
        report = asyncio.run(run_simulation(params))
    if report.error:
        st.error(report.error)
    else:
        st.subheader(report.question or report.slug)
        left, right, third = st.columns(3)
        left.metric("Kapanan PnL", f"{report.realized_pnl:.2f}")
        right.metric("Nakit", f"{report.cash:.2f}")
        third.metric("Karar", f"al {report.counts.get('buy', 0)} / sat {report.counts.get('sell', 0)} / bekle {report.counts.get('wait', 0)}")
        st.write(
            f"Katsayı kaynağı: {report.coefficient_source} | α={report.alpha:.4f} | β={report.beta:.4f} | "
            f"eski örnek {report.archive_samples}"
        )
        if report.open_position:
            st.warning("Açık pozisyon kâra yazılmadı.")
            st.json(report.open_position)
        else:
            st.success("Açık pozisyon yok.")
        st.write("Kapanan işlemler")
        if report.trades:
            st.dataframe(report.trades, use_container_width=True)
        else:
            st.write("Bu pencerede kapanan işlem yok.")
        with st.expander("Günlük"):
            st.code("\n".join(report.log))

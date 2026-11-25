import streamlit as st
import asyncio
from core import config
from simulation.run_paper import run_simulation

st.set_page_config(page_title="Polymarket Agents", layout="wide")
st.title("Polymarket Multi-Agent Paper Trader")

st.sidebar.header("Parameters")
config.ALPHA = st.sidebar.slider("Alpha", -0.05, 0.05, config.ALPHA, 0.001)
config.BETA = st.sidebar.slider("Beta", 0.05, 0.40, config.BETA, 0.01)
config.MIN_EDGE = st.sidebar.slider("Min Edge", 0.005, 0.05, config.MIN_EDGE, 0.001)
config.ROUND_TRIP_COST = st.sidebar.slider("Round Trip Cost", 0.005, 0.03, config.ROUND_TRIP_COST, 0.001)
config.MAX_POSITION_USDC = st.sidebar.slider("Max Position (USDC)", 10.0, 200.0, config.MAX_POSITION_USDC, 5.0)
config.MAX_HOLD_SECONDS = st.sidebar.slider("Max Hold (sec)", 15, 120, config.MAX_HOLD_SECONDS, 5)
config.VIRTUAL_BANKROLL = st.sidebar.number_input("Virtual Bankroll", 500.0, 10000.0, config.VIRTUAL_BANKROLL)

token_id = st.text_input("Token ID", placeholder="Paste Polymarket token ID")
duration = st.number_input("Duration (minutes)", 5, 120, 30)

if st.button("Start Paper Trading"):
    if not token_id:
        st.error("Token ID gerekli")
    else:
        with st.spinner("Running..."):
            portfolio = asyncio.run(run_simulation(token_id, duration))
            st.success(f"Finished. Final cash: {portfolio.cash:.2f}")
            st.json(portfolio.trades[-10:])

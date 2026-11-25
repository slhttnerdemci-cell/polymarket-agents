# Parameters the UI writes before a paper window starts.
# The hot loop reads a Params copy. It does not call an LLM.

ALPHA = 0.0
BETA = 0.15
MIN_EDGE = 0.012
BUFFER = 0.005
# Polymarket taker fee coefficient after 20 Nov 2026.
# BTC 5m/15m up/down is 0.05. Other crypto is 0.01.
FEE_RATE = 0.05
ADVERSE_MOVE = 0.05
RISK_FRACTION = 0.02
MAX_POSITION_USDC = 50.0
MAX_HOLD_SECONDS = 45.0
ENTRY_CUTOFF_SECONDS = 20.0
FORCE_FLATTEN_SECONDS = 8.0
PRESSURE_REVERSE_THRESHOLD = 0.35
IMBALANCE_DEPTH = 5
VIRTUAL_BANKROLL = 1000.0
POLL_INTERVAL = 2.0
TICK_SIZE = 0.01
MIN_SHARES = 5.0
MIN_FIT_SAMPLES = 8
ASSET = "btc"
WINDOW_SECONDS = 300
USE_ARCHIVE = True

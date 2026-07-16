import streamlit as st
import yfinance as yf
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import time

# --- 1. SETUP & SYMBOLS ---
st.set_page_config(page_title="Seasonality Dashboard Pro", layout="wide")

# Verified NIFTY 100 List (Moneycontrol/NSE 2026)
NIFTY100 = [
    "ABB", "ADANIENSOL", "ADANIENT", "ADANIGREEN", "ADANIPORTS", "ADANIPOWER", "ATGL",
    "AMBUJACEM", "APOLLOHOSP", "ASIANPAINT", "AXISBANK", "BAJAJ-AUTO", "BAJFINANCE",
    "BAJAJFINSV", "BAJAJHLDNG", "BANKBARODA", "BEL", "BPCL", "BHARTIARTL", "BOSCHLTD",
    "BRITANNIA", "CANBK", "CHOLAFIN", "CIPLA", "COALINDIA", "COLPAL", "DLF",
    "DABUR", "DIVISLAB", "DRREDDY", "EICHERMOT", "GAIL", "GODREJCP", "GRASIM",
    "HAL", "HAVELLS", "HCLTECH", "HDFCBANK", "HDFCLIFE", "HEROMOTOCO",
    "HINDALCO", "HINDUNILVR", "ICICIBANK", "ICICIGI", "ICICIPRULI", "IDFCFIRSTB", "ITC",
    "INDHOTEL", "INDUSINDBK", "INDUSTOWER", "INFY", "IOC", "IRCTC", "IRFC", "JSWSTEEL",
    "JINDALSTEL", "JIOFIN", "KOTAKBANK", "LTIM", "LT", "LICI", "M&M",
    "MARICO", "MARUTI", "NESTLEIND", "NTPC", "NYKAA", "ONGC", "PIDILITIND", 
    "PIIND", "PFC", "POWERGRID", "PNB", "RECLTD", "RELIANCE", "SBICARD",
    "SBILIFE", "SBIN", "SHREECEM", "SHRIRAMFIN", "SIEMENS", "SRF", "SUNPHARMA", 
    "TATACONSUM", "TATAMOTORS", "TATAPOWER", "TATASTEEL", "TCS", "TECHM", "TITAN", 
    "TORNTPHARM", "TRENT", "TVSMOTOR", "ULTRACEMCO", "UNITDSPR", "VBL", "VEDL", 
    "WIPRO", "ETERNAL", "ZYDUSLIFE"
]

MONTH_MAP = {
    "January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
    "July": 7, "August": 8, "September": 9, "October": 10, "November": 11, "December": 12
}

# --- 2. DATA ENGINES ---
@st.cache_data(ttl=300)
def get_daily_data(ticker, s_year):
    start_dt = f"{s_year}-01-01"
    try:
        data = yf.download(ticker, start=start_dt, interval="1d", progress=False, auto_adjust=True, multi_level_index=False)
        return data
    except: return pd.DataFrame()

@st.cache_data(ttl=300)
def get_first_hour_stats(ticker_ns, target_month_name):
    now = datetime.now()
    m_num = MONTH_MAP[target_month_name]
    if m_num > now.month: return None, None
    start_dt = datetime(now.year, m_num, 1)
    end_dt = start_dt + timedelta(days=7)
    try:
        intraday = yf.download(ticker_ns, start=start_dt, end=end_dt, interval="1h", progress=False, multi_level_index=False)
        if intraday.empty: return None, None
        return float(intraday['High'].iloc[0]), float(intraday['Close'].iloc[0])
    except: return None, None

# --- 3. HEATMAP GENERATOR ---
def show_seasonality_heatmap(ticker, s_year):
    data = get_daily_data(ticker, s_year)
    if data.empty: return
    
    # Calculate Monthly Returns
    monthly_data = data['Close'].resample('ME').last().pct_change() * 100
    df = monthly_data.to_frame(name='Return')
    df['Year'] = df.index.year
    df['Month'] = df.index.month
    
    # Pivot for Heatmap
    pivot = df.pivot(index='Year', columns='Month', values='Return')
    pivot.columns = [list(MONTH_MAP.keys())[m-1] for m in pivot.columns]
    
    # Plot
    st.write(f"### 🔥 Seasonality Heatmap: {ticker}")
    fig, ax = plt.subplots(figsize=(12, len(pivot) * 0.4 + 2))
    sns.heatmap(pivot, annot=True, fmt=".1f", cmap="RdYlGn", center=0, ax=ax, cbar_kws={'label': 'Return %'})
    plt.title(f"Monthly Returns (%) - {ticker}", fontsize=14)
    st.pyplot(fig)

# --- 4. SIDEBAR ---
st.sidebar.header("🔍 Filters")
current_yr = datetime.now().year
start_year = st.sidebar.selectbox("History Start Year:", range(2000, current_yr), index=range(2000, current_yr).index(2008))
selected_month = st.sidebar.selectbox("Analyze Month:", list(MONTH_MAP.keys()), index=list(MONTH_MAP.keys()).index(datetime.now().strftime('%B')))
win_min = st.sidebar.slider("Min Win Rate %", 50, 100, 70)
refresh_val = st.sidebar.selectbox("Auto-Refresh:", ["5 min", "10 min", "Manual Only"])

# --- 5. MAIN ANALYSIS ---
st.subheader(f"🎯 {selected_month} Seasonality Dashboard")
st.caption(f"Historical Basis: {start_year} to {current_yr} | Click a row to see the Heatmap")

results = []
bar = st.progress(0)
for idx, sym in enumerate(NIFTY100):
    ticker = sym + ".NS"
    data = get_daily_data(ticker, start_year)
    if data.empty: continue

    m_rets = data['Close'].resample('ME').last().pct_change() * 100
    df_rets = m_rets.dropna().to_frame(name='Ret')
    df_rets['MonthName'] = df_rets.index.month_name()
    m_data = df_rets[df_rets['MonthName'] == selected_month]
    
    if not m_data.empty:
        pos_yrs = len(m_data[m_data['Ret'] > 0])
        tot_yrs = len(m_data)
        win_rate = (pos_yrs / tot_yrs) * 100
        if win_rate >= win_min:
            fh_high, fh_close = get_first_hour_stats(ticker, selected_month)
            curr_price = float(data['Close'].iloc[-1])
            status = "🚀 BREAKOUT" if (fh_high and curr_price > fh_high) else "WAITING"
            if MONTH_MAP[selected_month] > datetime.now().month: status = "⌛ UPCOMING"

            results.append({
                'Ticker': sym, 'Status': status, 'Win_Rate_%': round(win_rate, 1),
                'Positive_Years': f"{pos_yrs} / {tot_yrs}", 'Avg_Return_%': round(m_data['Ret'].mean(), 2),
                'MTD_Gain_%': round(((curr_price / fh_close) - 1) * 100, 2) if (fh_close and fh_close > 0) else 0,
                'Current_Price': round(curr_price, 2), '1H_High': round(fh_high, 2) if fh_high else 0
            })
    bar.progress((idx + 1) / len(NIFTY100))
bar.empty()

# --- 6. DISPLAY & SELECTION ---
if results:
    df_final = pd.DataFrame(results).sort_values(by=["Status", "Win_Rate_%"], ascending=[True, False])
    
    # Enable Row Selection
    selection_event = st.dataframe(
        df_final.style.map(lambda x: 'background-color: #1b5e20; color: white' if x == "🚀 BREAKOUT" else ('color: #00d4ff' if x == "⌛ UPCOMING" else 'color: #ffa000'), subset=['Status']),
        use_container_width=True, 
        height=400,
        on_select="rerun",
        selection_mode="single-row"
    )

    # If a row is selected, show heatmap
    if selection_event.selection.rows:
        selected_idx = selection_event.selection.rows[0]
        selected_ticker = df_final.iloc[selected_idx]['Ticker']
        show_seasonality_heatmap(selected_ticker + ".NS", start_year)
else:
    st.warning("No results found matching criteria.")

# Auto-Refresh
if "Manual" not in refresh_val:
    time.sleep(300 if "5" in refresh_val else 600)
    st.rerun()

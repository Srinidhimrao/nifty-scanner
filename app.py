import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import time

# --- 1. SETUP & SYMBOLS ---
st.set_page_config(page_title="Seasonality Dashboard Pro", layout="wide")

# Verified NIFTY 100 List (Moneycontrol/NSE July 2026)
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

# --- 2. DATA FUNCTIONS ---
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

# --- 3. SIDEBAR ---
st.sidebar.header("🔍 Filters")
current_yr = datetime.now().year
start_year = st.sidebar.selectbox("History Start Year:", range(2000, current_yr), index=range(2000, current_yr).index(2008))

current_month_name = datetime.now().strftime('%B')
selected_month = st.sidebar.selectbox("Analyze Month:", list(MONTH_MAP.keys()), index=list(MONTH_MAP.keys()).index(current_month_name))

win_min = st.sidebar.slider("Min Win Rate %", 50, 100, 70)
refresh_val = st.sidebar.selectbox("Auto-Refresh:", ["5 min", "10 min", "Manual Only"])

# --- 4. ANALYSIS ---
def run_analysis():
    st.subheader(f"🎯 {selected_month} Seasonality Dashboard")
    st.caption(f"Historical Basis: {start_year} to {current_yr} | Index: Nifty 100")

    results = []
    bar = st.progress(0)
    status_msg = st.empty()

    for idx, sym in enumerate(NIFTY100):
        ticker = sym + ".NS"
        status_msg.text(f"Scanning {sym}...")
        
        data = get_daily_data(ticker, start_year)
        if data.empty: continue

        # Seasonality Calculation
        m_rets = data['Close'].resample('ME').last().pct_change() * 100
        df_rets = m_rets.dropna().to_frame(name='Ret')
        df_rets['MonthName'] = df_rets.index.month_name()

        # Group data for the selected month
        m_data = df_rets[df_rets['MonthName'] == selected_month]
        
        if not m_data.empty:
            total_years = len(m_data)
            positive_years = len(m_data[m_data['Ret'] > 0])
            win_rate = (positive_years / total_years) * 100

            if win_rate >= win_min:
                fh_high, fh_close = get_first_hour_stats(ticker, selected_month)
                curr_price = float(data['Close'].iloc[-1])
                
                # Logic for status
                if MONTH_MAP[selected_month] > datetime.now().month:
                    status = "⌛ UPCOMING"
                elif fh_high:
                    status = "🚀 BREAKOUT" if curr_price > fh_high else "WAITING"
                else:
                    status = "⚠️ NO DATA"

                results.append({
                    'Ticker': sym,
                    'Status': status,
                    'Win_Rate_%': round(win_rate, 1),
                    'Positive_Years': f"{positive_years} / {total_years}",
                    'Avg_Return_%': round(m_data['Ret'].mean(), 2),
                    'MTD_Gain_%': round(((curr_price / fh_close) - 1) * 100, 2) if (fh_close and fh_close > 0) else 0,
                    'Current_Price': round(curr_price, 2),
                    '1H_High': round(fh_high, 2) if fh_high else 0
                })
        bar.progress((idx + 1) / len(NIFTY100))
    
    bar.empty()
    status_msg.empty()

    if results:
        df_final = pd.DataFrame(results).sort_values(by=["Status", "Win_Rate_%"], ascending=[True, False])
        
        def style_status(val):
            if val == "🚀 BREAKOUT": return 'background-color: #1b5e20; color: white'
            if val == "⌛ UPCOMING": return 'color: #00d4ff'
            return 'color: #ffa000'

        st.dataframe(
            df_final.style.map(style_status, subset=['Status']), 
            use_container_width=True, 
            height=650
        )
    else:
        st.warning(f"No results for {selected_month} with >{win_min}% Win Rate.")

# --- 5. RUN & AUTO-REFRESH ---
run_analysis()

if "Manual" not in refresh_val:
    t = 300 if "5" in refresh_val else 600
    time.sleep(t)
    st.rerun()

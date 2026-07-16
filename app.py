import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Nifty Seasonality Pro", layout="wide")

NIFTY100 = [
    "ABB", "ABBOTINDIA", "ADANIENT", "ADANIGREEN", "ADANIPORTS", "ADANIPOWER", "ATGL",
    "AMBUJACEM", "APOLLOHOSP", "ASIANPAINT", "AXISBANK", "BAJAJ-AUTO", "BAJFINANCE",
    "BAJAJFINSV", "BAJAJHLDNG", "BANKBARODA", "BEL", "BERGEPAINT", "BHARTIARTL", "BIOCON",
    "BPCL", "BRITANNIA", "CANBK", "CHOLAFIN", "CIPLA", "COALINDIA", "COLPAL", "DLF",
    "DABUR", "DIVISLAB", "DRREDDY", "EICHERMOT", "GAIL", "GLAND", "GODREJCP", "GRASIM",
    "GUJGASLTD", "HAL", "HAVELLS", "HCLTECH", "HDFCBANK", "HDFCLIFE", "HEROMOTOCO",
    "HINDALCO", "HINDUNILVR", "ICICIBANK", "ICICIGI", "ICICIPRULI", "IDFCFIRSTB", "ITC",
    "INDHOTEL", "INDUSINDBK", "INDUSTOWER", "INFY", "IOC", "IRCTC", "IRFC", "JSWSTEEL",
    "JINDALSTEL", "JIOFIN", "JUBLFOOD", "KOTAKBANK", "LTIM", "LT", "LICI", "M&M",
    "MARICO", "MARUTI", "NESTLEIND", "NTPC", "NYKAA", "ONGC", "PAGEIND",
    "PIDILITIND", "PIIND", "PFC", "POWERGRID", "PNB", "RECLTD", "RELIANCE", "SBICARD",
    "SBILIFE", "SBIN", "SRF", "SHREECEM", "SIEMENS", "SUNPHARMA", "TATACONSUM", "TATAELXSI",
    "TATAMOTORS", "TATAPOWER", "TATASTEEL", "TCS", "TECHM", "TITAN", "TORNTPHARM", "TRENT",
    "TVSMOTOR", "ULTRACEMCO", "UNITDSPR", "VBL", "VEDL", "WIPRO", "ZOMATO", "ZYDUSLIFE"
]

MONTH_MAP = {
    "January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
    "July": 7, "August": 8, "September": 9, "October": 10, "November": 11, "December": 12
}

# --- 2. DATA ENGINES ---
@st.cache_data(ttl=300)
def get_daily_data(ticker, start_year):
    start_date = f"{start_year}-01-01"
    try:
        df = yf.download(ticker, start=start_date, interval="1d", progress=False, auto_adjust=True, multi_level_index=False)
        return df
    except:
        return pd.DataFrame()

@st.cache_data(ttl=300)
def get_first_hour_high(ticker_ns, target_month_name):
    """Gets the High of the 1st trading hour of the selected month in the CURRENT year."""
    now = datetime.now()
    m_num = MONTH_MAP[target_month_name]
    
    # If the month hasn't started yet in the current year, return None
    if m_num > now.month:
        return None, None
        
    start_dt = datetime(now.year, m_num, 1)
    end_dt = start_dt + timedelta(days=7) # First week to capture first trading day
    try:
        # Fetch 1-hour interval data
        intraday = yf.download(ticker_ns, start=start_dt, end=end_dt, interval="1h", progress=False, multi_level_index=False)
        if intraday.empty: return None, None
        
        # High and Close of the very first hour session
        return float(intraday['High'].iloc[0]), float(intraday['Close'].iloc[0])
    except:
        return None, None

# --- 3. SIDEBAR ---
st.sidebar.header("🔍 Filter Options")

current_yr = datetime.now().year
start_year = st.sidebar.selectbox("History Start Year:", range(current_yr-25, current_yr), index=7)

current_month_name = datetime.now().strftime('%B')
target_month = st.sidebar.selectbox("Analyze Month:", list(MONTH_MAP.keys()), index=list(MONTH_MAP.keys()).index(current_month_name))

min_win_rate = st.sidebar.slider("Minimum Historical Win Rate %", 50, 100, 70)
refresh_rate = st.sidebar.selectbox("Auto-Refresh:", ["5 min", "10 min", "Manual"])

# --- 4. CORE LOGIC ---
def run_analysis():
    st.subheader(f"📊 {target_month} Seasonality Dashboard (Since {start_year})")
    st.info(f"Live Price compared against the 1st hour high of {target_month} {current_yr}")
    
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()

    for idx, sym in enumerate(NIFTY100):
        ticker = sym + ".NS"
        status_text.text(f"Scanning {sym}...")
        
        # 1. Fetch Data
        df = get_daily_data(ticker, start_year)
        if df.empty or len(df) < 20: continue
        
        # 2. Get Live Current Price
        curr_price = float(df['Close'].iloc[-1])
        
        # 3. Calculate Seasonality (Completed Months Only)
        # Resample to Monthly and calculate Returns
        monthly_df = df['Close'].resample('ME').last().pct_change() * 100
        returns_df = monthly_df.dropna().to_frame(name='Ret')
        returns_df['Month'] = returns_df.index.month_name()
        returns_df['Year'] = returns_df.index.year
        
        # EXCLUDE the current year to prevent partial-month bias in Win Rate
        hist_returns = returns_df[returns_df['Year'] < current_yr]
        
        # Filter for the target month across all historical years
        m_hist = hist_returns[hist_returns['Month'] == target_month]
        
        if not m_hist.empty:
            total_years = len(m_hist)
            win_years = len(m_hist[m_hist['Ret'] > 0])
            win_rate = (win_years / total_years) * 100
            avg_ret = m_hist['Ret'].mean()
            
            if win_rate >= min_win_rate:
                # 4. Check for Breakout (Live Data)
                fh_high, fh_close = get_first_hour_high(ticker, target_month)
                
                # Logic for status
                m_num = MONTH_MAP[target_month]
                c_num = datetime.now().month
                
                if m_num > c_num:
                    status = "⌛ UPCOMING"
                elif fh_high:
                    status = "🚀 BREAKOUT" if curr_price > fh_high else "WAITING"
                else:
                    status = "⚠️ NO DATA"
                
                results.append({
                    'Ticker': sym,
                    'Status': status,
                    'Win_Rate_%': round(win_rate, 1),
                    'Avg_Hist_Ret_%': round(avg_ret, 2),
                    'Current_Price': round(curr_price, 2),
                    'MTD_Gain_%': round(((curr_price / fh_close) - 1) * 100, 2) if fh_close else 0,
                    '1H_High_Lvl': round(fh_high, 2) if fh_high else 0,
                    'Years_Sampled': total_years
                })
        
        progress_bar.progress((idx + 1) / len(NIFTY100))

    status_text.empty()
    progress_bar.empty()

    if results:
        final_df = pd.DataFrame(results).sort_values(by=["Status", "Win_Rate_%"], ascending=[True, False])
        
        # Styling
        def style_rows(val):
            if val == "🚀 BREAKOUT": return 'background-color: #1b5e20; color: white; font-weight: bold'
            if val == "⌛ UPCOMING": return 'color: #00d4ff'
            if val == "WAITING": return 'color: #ffa000'
            return ''

        st.dataframe(final_df.style.map(style_rows, subset=['Status']), use_container_width=True, height=600)
    else:
        st.warning(f"No stocks found with Win Rate >= {min_win_rate}% for {target_month}.")

# --- 5. EXECUTE & REFRESH ---
run_analysis()

if "Manual" not in refresh_rate:
    t = 300 if "5" in refresh_rate else 600
    time.sleep(t)
    st.rerun()

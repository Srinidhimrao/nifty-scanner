import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import time

# 1. Setup Page
st.set_page_config(page_title="Live Seasonality Dashboard", layout="wide")

# 2. Optimized Data Fetching
@st.cache_data(ttl=300) 
def get_stock_data(ticker, start_date):
    try:
        # Added multi_level_index=False to prevent MultiIndex errors in newer yfinance versions
        data = yf.download(ticker, start=start_date, interval="1d", progress=False, auto_adjust=True, multi_level_index=False)
        return data
    except:
        return pd.DataFrame()

@st.cache_data(ttl=300)
def get_first_hour_stats(ticker_ns):
    now = datetime.now()
    start_dt = datetime(now.year, now.month, 1)
    end_dt = start_dt + timedelta(days=7)
    try:
        # Added multi_level_index=False here as well
        intraday = yf.download(ticker_ns, start=start_dt, end=end_dt, interval="1h", progress=False, multi_level_index=False)
        if intraday.empty: return None, None
        return float(intraday['High'].iloc[0]), float(intraday['Close'].iloc[0])
    except: return None, None

# 3. Sidebar UI
st.sidebar.header("Settings")
win_min = st.sidebar.slider("Min Win Rate %", 50, 100, 70)
refresh_interval = st.sidebar.selectbox("Auto-Refresh Every:", ["5 min", "10 min", "Manual Only"])

# 4. Main App Logic
def run_main_analysis():
    current_month = datetime.now().strftime('%B')
    start_18y = (datetime.now() - timedelta(days=18*365)).strftime('%Y-%m-%d')
    
    st.subheader(f"📊 {current_month} Analysis - Updated: {datetime.now().strftime('%H:%M:%S')}")
    
    results = []
    progress_text = st.empty()
    bar = st.progress(0)
    
    # Use your full NIFTY100 list here
    SYMBOLS = [
    "ABB", "ABBOTINDIA", "ADANIENT", "ADANIGREEN", "ADANIPORTS", "ADANIPOWER", "ATGL", 
    "AMBUJACEM", "APOLLOHOSP", "ASIANPAINT", "AXISBANK", "BAJAJ-AUTO", "BAJFINANCE", 
    "BAJAJFINSV", "BAJAJHLDNG", "BANKBARODA", "BEL", "BERGEPAINT", "BHARTIARTL", "BIOCON", 
    "BPCL", "BRITANNIA", "CANBK", "CHOLAFIN", "CIPLA", "COALINDIA", "COLPAL", "DLF", 
    "DABUR", "DIVISLAB", "DRREDDY", "EICHERMOT", "GAIL", "GLAND", "GODREJCP", "GRASIM", 
    "GUJGASLTD", "HAL", "HAVELLS", "HCLTECH", "HDFCBANK", "HDFCLIFE", "HEROMOTOCO", 
    "HINDALCO", "HINDUNILVR", "ICICIBANK", "ICICIGI", "ICICIPRULI", "IDFCFIRSTB", "ITC", 
    "INDHOTEL", "INDUSINDBK", "INDUSTOWER", "INFY", "IOC", "IRCTC", "IRFC", "JSWSTEEL", 
    "JINDALSTEL", "JIOFIN", "JUBLFOOD", "KOTAKBANK", "LTIM", "LT", "LICI", "M&M", 
    "MARICO", "MARUTI", "NESTLEIND", "NTPC", "NYKAA", "ONGC", "PAGEIND", "PANAMAPET", 
    "PIDILITIND", "PIIND", "PFC", "POWERGRID", "PNB", "RECLTD", "RELIANCE", "SBICARD", 
    "SBILIFE", "SBIN", "SRF", "SHREECEM", "SIEMENS", "SUNPHARMA", "TATACONSUM", "TATAELXSI", 
    "TATAMOTORS", "TATAPOWER", "TATASTEEL", "TCS", "TECHM", "TITAN", "TORNTPHARM", "TRENT", 
    "TVSMOTOR", "ULTRACEMCO", "UNITDSPR", "VBL", "VEDL", "WIPRO", "ZOMATO", "ZYDUSLIFE"
    ]

    for idx, sym in enumerate(symbols):
        ticker = sym + ".NS"
        progress_text.text(f"Scanning {sym}...")
        
        data = get_stock_data(ticker, start_18y)
        if data.empty: continue

        # Seasonality Calculation
        m_rets = data['Close'].resample('ME').last().pct_change() * 100
        df_rets = m_rets.dropna().to_frame(name='Ret')
        df_rets['Month'] = df_rets.index.month_name()

        stats = df_rets.groupby('Month')['Ret'].agg(['mean', 'count']).reset_index()
        wins = df_rets[df_rets['Ret'] > 0].groupby('Month')['Ret'].count().reset_index()
        wins.columns = ['Month', 'Win_Count']
        stats = pd.merge(stats, wins, on='Month', how='left').fillna(0)
        stats['Win_Rate_%'] = (stats['Win_Count'] / stats['count']) * 100

        # Safety check: ensure month exists in history
        if current_month in stats['Month'].values:
            m_stat = stats[stats['Month'] == current_month].iloc[0]

            if m_stat['Win_Rate_%'] >= win_min:
                fh_high, fh_close = get_first_hour_stats(ticker)
                curr_price = float(data['Close'].iloc[-1])
                status = "🚀 BREAKOUT" if fh_high and curr_price > fh_high else "WAITING"

                results.append({
                    'Ticker': sym,
                    'Status': status,
                    'Win_Rate_%': round(m_stat['Win_Rate_%'], 1),
                    'MTD_Gain_%': round(((curr_price / fh_close) - 1) * 100, 2) if fh_close else 0,
                    'Current_Price': round(curr_price, 2),
                    '1H_High': round(fh_high, 2) if fh_high else 0,
                    'Years': int(m_stat['count'])
                })
        bar.progress((idx + 1) / len(symbols))
    
    bar.empty()
    progress_text.empty()

    if results:
        df_final = pd.DataFrame(results).sort_values(by="Status", ascending=False)
        
        # --- THE FIX IS HERE ---
        # Changed .applymap() to .map()
        def style_status(val):
            if val == "🚀 BREAKOUT":
                return 'background-color: #1b5e20; color: white; font-weight: bold'
            return 'color: #ffa000'

        st.dataframe(
            df_final.style.map(style_status, subset=['Status']),
            use_container_width=True,
            height=600
        )
    else:
        st.warning("No stocks found matching the criteria.")

# Execute
run_main_analysis()

# Auto-Refresh Logic
if "Manual" not in refresh_interval:
    sleep_time = 300 if "5" in refresh_interval else 600
    time.sleep(sleep_time)
    st.rerun()

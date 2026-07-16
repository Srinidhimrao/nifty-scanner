import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import time

# 1. Setup Page
st.set_page_config(page_title="Seasonality Scanner", layout="wide")

# Month mapping for calculations
MONTH_MAP = {
    "January": 1, "February": 2, "March": 3, "April": 4,
    "May": 5, "June": 6, "July": 7, "August": 8,
    "September": 9, "October": 10, "November": 11, "December": 12
}

# 2. Optimized Data Fetching
@st.cache_data(ttl=300) 
def get_stock_data(ticker, start_date):
    try:
        data = yf.download(ticker, start=start_date, interval="1d", progress=False, auto_adjust=True, multi_level_index=False)
        return data
    except:
        return pd.DataFrame()

@st.cache_data(ttl=300)
def get_month_opening_stats(ticker_ns, target_month_name):
    """Gets the high of the 1st hour of the 1st trading day of the SPECIFIED month in the CURRENT year."""
    now = datetime.now()
    target_month_num = MONTH_MAP[target_month_name]
    
    # Define search window for the first trading day of that month
    start_dt = datetime(now.year, target_month_num, 1)
    
    # If the selected month is in the future, we can't get breakout data
    if start_dt > now:
        return None, None
        
    end_dt = start_dt + timedelta(days=7) # Look at the first week to find the first trading session
    try:
        intraday = yf.download(ticker_ns, start=start_dt, end=end_dt, interval="1h", progress=False, multi_level_index=False)
        if intraday.empty: return None, None
        return float(intraday['High'].iloc[0]), float(intraday['Close'].iloc[0])
    except: return None, None

# 3. Sidebar UI
st.sidebar.header("🎯 Analysis Settings")

# Month Selection Logic
current_month_name = datetime.now().strftime('%B')
month_options = ["Current Month (" + current_month_name + ")"] + list(MONTH_MAP.keys())
selected_option = st.sidebar.selectbox("Target Month for Analysis:", month_options)

# Determine target month
if "Current Month" in selected_option:
    target_month = current_month_name
else:
    target_month = selected_option

win_min = st.sidebar.slider("Min Historical Win Rate %", 50, 100, 70)
refresh_interval = st.sidebar.selectbox("Auto-Refresh Live Data:", ["5 min", "10 min", "Manual Only"])

# 4. Main App Logic
def run_main_analysis(target_month):
    start_18y = (datetime.now() - timedelta(days=18*365)).strftime('%Y-%m-%d')
    
    st.subheader(f"📊 {target_month} Seasonality Analysis")
    st.caption(f"Showing stocks that historically perform best in {target_month} | Data updated: {datetime.now().strftime('%H:%M:%S')}")
    
    results = []
    progress_text = st.empty()
    bar = st.progress(0)
    
    # Use your full NIFTY100 list
    symbols = [    "ABB", "ABBOTINDIA", "ADANIENT", "ADANIGREEN", "ADANIPORTS", "ADANIPOWER", "ATGL", 
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
    "TVSMOTOR", "ULTRACEMCO", "UNITDSPR", "VBL", "VEDL", "WIPRO", "ZOMATO", "ZYDUSLIFE"] 

    for idx, sym in enumerate(symbols):
        ticker = sym + ".NS"
        progress_text.text(f"Analyzing {sym} for {target_month}...")
        
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

        # Filter for the target month
        if target_month in stats['Month'].values:
            m_stat = stats[stats['Month'] == target_month].iloc[0]

            if m_stat['Win_Rate_%'] >= win_min:
                fh_high, fh_close = get_month_opening_stats(ticker, target_month)
                curr_price = float(data['Close'].iloc[-1])
                
                # Logic for Status
                if fh_high is None:
                    status = "⌛ FUTURE" if MONTH_MAP[target_month] > datetime.now().month else "⚠️ NO DATA"
                else:
                    status = "🚀 BREAKOUT" if curr_price > fh_high else "WAITING"

                results.append({
                    'Ticker': sym,
                    'Status': status,
                    'Win_Rate_%': round(m_stat['Win_Rate_%'], 1),
                    'Hist_Avg_Ret_%': round(m_stat['mean'], 2),
                    'MTD_Gain_%': round(((curr_price / fh_close) - 1) * 100, 2) if fh_close else 0,
                    'Current_Price': round(curr_price, 2),
                    'Month_Start_High': round(fh_high, 2) if fh_high else 0,
                    'Years_Back': int(m_stat['count'])
                })
        bar.progress((idx + 1) / len(symbols))
    
    bar.empty()
    progress_text.empty()

    if results:
        df_final = pd.DataFrame(results).sort_values(by=["Status", "Win_Rate_%"], ascending=[True, False])
        
        def style_status(val):
            if val == "🚀 BREAKOUT": return 'background-color: #1b5e20; color: white'
            if val == "⌛ FUTURE": return 'color: #888888'
            return 'color: #ffa000'

        st.dataframe(
            df_final.style.map(style_status, subset=['Status']),
            use_container_width=True,
            height=600
        )
    else:
        st.warning(f"No stocks found with a >{win_min}% win rate in {target_month}.")

# Execute Analysis
run_main_analysis(target_month)

# Auto-Refresh Logic
if "Manual" not in refresh_interval:
    sleep_time = 300 if "5" in refresh_interval else 600
    time.sleep(sleep_time)
    st.rerun()

import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import time

# --- 1. SETUP ---
st.set_page_config(page_title="Seasonality & Breakout Dashboard", layout="wide")

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
def fetch_raw_data(ticker, start_date):
    try:
        df = yf.download(ticker, start=start_date, interval="1d", progress=False, auto_adjust=True, multi_level_index=False)
        return df
    except:
        return pd.DataFrame()

@st.cache_data(ttl=300)
def get_anchor_stats(ticker_ns, target_month_name):
    """Fetches High/Close of the 1st hour of the 1st trading day of the selected month in CURRENT year."""
    now = datetime.now()
    month_num = MONTH_MAP[target_month_name]
    
    # If target month is in future
    if month_num > now.month:
        return None, None
        
    start_dt = datetime(now.year, month_num, 1)
    end_dt = start_dt + timedelta(days=7) 
    try:
        intraday = yf.download(ticker_ns, start=start_dt, end=end_dt, interval="1h", progress=False, multi_level_index=False)
        if intraday.empty: return None, None
        return float(intraday['High'].iloc[0]), float(intraday['Close'].iloc[0])
    except: return None, None

# --- 3. SIDEBAR ---
st.sidebar.header("🛠️ Configuration")

# Year Selector
curr_yr = datetime.now().year
start_yr = st.sidebar.selectbox("History Start Year:", range(curr_yr-25, curr_yr), index=7)

# Month Selector
curr_month_name = datetime.now().strftime('%B')
selected_month = st.sidebar.selectbox("Target Month Analysis:", list(MONTH_MAP.keys()), index=list(MONTH_MAP.keys()).index(curr_month_name))

win_min = st.sidebar.slider("Min Win Rate %", 50, 100, 70)
refresh_choice = st.sidebar.selectbox("Refresh Frequency:", ["5 min", "10 min", "Manual"])

# --- 4. ANALYTICS ---
def run_analysis(target_m, s_year):
    start_date = f"{s_year}-01-01"
    st.subheader(f"📈 {target_m} Dashboard (Since {s_year})")
    st.caption(f"Latest Market Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = []
    prog = st.progress(0)
    status_text = st.empty()

    for idx, sym in enumerate(NIFTY100):
        ticker = sym + ".NS"
        status_text.text(f"Processing {sym}...")
        
        # 1. Get Daily Data
        raw_df = fetch_raw_data(ticker, start_date)
        if raw_df.empty or len(raw_df) < 10: continue
        
        # --- LATEST CURRENT DATA ---
        # We grab the last available price before resampling
        current_price = float(raw_df['Close'].iloc[-1])
        
        # 2. Seasonality (using completed months only)
        # We exclude the current partial month from historical win rate stats
        completed_months_df = raw_df[:raw_df.index[-1].strftime('%Y-%m-01')]
        if not completed_months_df.empty:
            m_rets = completed_months_df['Close'].resample('ME').last().pct_change() * 100
            df_rets = m_rets.dropna().to_frame(name='Ret')
            df_rets['MonthName'] = df_rets.index.month_name()

            stats = df_rets.groupby('MonthName')['Ret'].agg(['mean', 'count']).reset_index()
            wins = df_rets[df_rets['Ret'] > 0].groupby('MonthName')['Ret'].count().reset_index()
            wins.columns = ['MonthName', 'Win_Count']
            stats = pd.merge(stats, wins, on='MonthName', how='left').fillna(0)
            stats['WinRate'] = (stats['Win_Count'] / stats['count']) * 100
            
            # Check if target month meets criteria
            month_stats = stats[stats['MonthName'] == target_m]
            if not month_stats.empty:
                m_stat = month_stats.iloc[0]
                
                if m_stat['WinRate'] >= win_min:
                    # 3. Get Breakout Anchor (First Hour of Target Month)
                    fh_high, fh_close = get_anchor_stats(ticker, target_m)
                    
                    # 4. Determine Status based on LATEST PRICE
                    t_month_num = MONTH_MAP[target_m]
                    c_month_num = datetime.now().month
                    
                    if t_month_num > c_month_num:
                        status = "⌛ UPCOMING"
                    elif fh_high:
                        status = "🚀 BREAKOUT" if current_price > fh_high else "WAITING"
                    else:
                        status = "⚠️ NO DATA"

                    results.append({
                        'Ticker': sym,
                        'Status': status,
                        'Win_Rate_%': round(m_stat['WinRate'], 1),
                        'Avg_Return_%': round(m_stat['mean'], 2),
                        'Current_Price': round(current_price, 2),
                        'MTD_Gain_%': round(((current_price / fh_close) - 1) * 100, 2) if (fh_close and fh_close > 0) else 0,
                        '1H_High_Lvl': round(fh_high, 2) if fh_high else 0,
                        'Sample_Years': int(m_stat['count'])
                    })
        
        prog.progress((idx + 1) / len(NIFTY100))
    
    prog.empty()
    status_text.empty()

    if results:
        df_final = pd.DataFrame(results).sort_values(by=["Status", "Win_Rate_%"], ascending=[True, False])
        
        def color_logic(val):
            if val == "🚀 BREAKOUT": return 'background-color: #1b5e20; color: white; font-weight: bold'
            if val == "⌛ UPCOMING": return 'color: #00d4ff'
            if val == "WAITING": return 'color: #ffa000'
            return ''

        st.dataframe(df_final.style.map(color_logic, subset=['Status']), use_container_width=True, height=600)
    else:
        st.warning(f"No results for {target_m} with Win Rate > {win_min}%")

# --- 5. EXECUTION ---
run_analysis(selected_month, start_yr)

if "Manual" not in refresh_choice:
    t = 300 if "5" in refresh_choice else 600
    time.sleep(t)
    st.rerun()

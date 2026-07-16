import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

# --- CONFIGURATION ---
st.set_page_config(page_title="Nifty 100 Seasonality", layout="wide")

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

def get_first_hour_stats(ticker):
    now = datetime.now()
    start_dt = datetime(now.year, now.month, 1)
    end_dt = start_dt + timedelta(days=7)
    data = yf.download(ticker, start=start_dt, end=end_dt, interval="1h", progress=False)
    if data.empty: return None, None
    if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.get_level_values(0)
    return float(data['High'].iloc[0]), float(data['Close'].iloc[0])

def run_scanner():
    results = []
    current_month = datetime.now().strftime('%B')
    start_18y = (datetime.now() - timedelta(days=18*365)).strftime('%Y-%m-%d')

    for sym in SYMBOLS:
        ticker = f"{sym}.NS"
        try:
            data = yf.download(ticker, start=start_18y, interval="1d", progress=False, auto_adjust=True)
            if data.empty: continue
            if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.get_level_values(0)

            m_rets = data['Close'].resample('ME').last().pct_change() * 100
            df = m_rets.dropna().to_frame(name='Ret')
            df['Month'] = df.index.month_name()
            
            stats = df.groupby('Month')['Ret'].agg(['mean', 'count']).reset_index()
            wins = df[df['Ret'] > 0].groupby('Month')['Ret'].count().reset_index()
            wins.columns = ['Month', 'Win_Count']
            stats = pd.merge(stats, wins, on='Month', how='left').fillna(0)
            stats['Win_Rate_%'] = (stats['Win_Count'] / stats['count']) * 100

            m_stat = stats[stats['Month'] == current_month].iloc[0]
            
            # Filter: Win Rate > 70%
            if m_stat['Win_Rate_%'] >= 70:
                fh_high, fh_close = get_first_hour_stats(ticker)
                curr_price = float(data['Close'].iloc[-1])
                
                status = "🚀 BREAKOUT" if fh_high and curr_price > fh_high else "WAITING"
                
                results.append({
                    'Ticker': sym,
                    'Status': status,
                    'Win_Rate_%': m_stat['Win_Rate_%'],
                    'Hist_Avg_%': m_stat['mean'],
                    '1H_High': fh_high,
                    'Price': curr_price,
                    'MTD_%': ((curr_price / fh_close) - 1) * 100 if fh_close else 0
                })
        except: continue
    return pd.DataFrame(results)

# --- WEB UI ---
st.title("🎯 Nifty 100 Seasonality Dashboard")
st.write(f"Live Analysis for **{datetime.now().strftime('%B %Y')}** (Data anchored to 1st Hour High)")

if st.button('🔄 Refresh Live Market Data'):
    st.cache_data.clear()

with st.spinner('Scanning NSE stocks... this takes 1-2 minutes.'):
    df = run_scanner()

if not df.empty:
    # Color coding for the Status column
    def color_status(val):
        color = '#27ae60' if val == "🚀 BREAKOUT" else '#f39c12'
        return f'color: white; background-color: {color}; font-weight: bold'

    df = df.sort_values(by=['Status', 'Win_Rate_%'], ascending=[False, False])
    
    st.dataframe(df.style.applymap(color_status, subset=['Status'])
                 .format({"Win_Rate_%": "{:.1f}%", "Hist_Avg_%": "{:.2f}%", "MTD_%": "{:.2f}%"}), 
                 use_container_width=True)
else:
    st.info("No active opportunities found with >70% Win Rate for this month.")
import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta

def calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period-1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period-1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

st.title("Debug Scanner v2")

sym = st.selectbox("เลือกหุ้น", ["CPALL.BK", "HUMAN.BK"])
scan_days = 90

if st.button("Debug!"):
    end = datetime.today()
    start = end - timedelta(days=scan_days + 180)
    df = yf.download(sym, start=start, end=end, auto_adjust=False, progress=False)
    df = df[["Open","High","Low","Close","Volume"]].copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.dropna(inplace=True)
    df["RSI"] = calc_rsi(df["Close"])

    window = df.iloc[-scan_days:]
    atl_idx = window["Close"].idxmin()
    atl_price = float(df.loc[atl_idx, "Close"])
    atl_rsi = float(df.loc[atl_idx, "RSI"])

    st.write(f"**Total df rows:** {len(df)}")
    st.write(f"**Window start:** {window.index[0].date()}")
    st.write(f"**ATL date:** {atl_idx.date()}, price: {atl_price:.2f}, RSI: {atl_rsi:.1f}")

    atl_pos = df.index.get_loc(atl_idx)
    st.write(f"**atl_pos (iloc):** {atl_pos}")
    st.write(f"**df.iloc[atl_pos] date:** {df.index[atl_pos].date()}, price: {float(df.iloc[atl_pos]['Close']):.2f}")

    scan = df.iloc[atl_pos + 1:]
    st.write(f"**scan rows:** {len(scan)}, from {scan.index[0].date()} to {scan.index[-1].date()}")

    current_state = "FIND_B"
    b_price = None
    b_rsi = None
    b_idx = None

    for idx, row in scan.iterrows():
        close = float(row["Close"])
        rsi_val = row["RSI"]
        if pd.isna(rsi_val): continue
        rsi = float(rsi_val)

        if current_state == "FIND_B":
            diff = rsi - atl_rsi
            if diff >= 8:
                b_price = close
                b_rsi = rsi
                b_idx = idx
                current_state = "CONFIRM_B"
                st.success(f"A ยืนยัน! ว่าที่ B = {b_price:.2f}, RSI={b_rsi:.1f}, date={b_idx.date()}")

        elif current_state == "CONFIRM_B":
            if close > b_price:
                old = b_price
                b_price = close
                b_rsi = rsi
                b_idx = idx
                st.warning(f"ยกเลิก ว่าที่ B {old:.2f} → ว่าที่ B ใหม่ = {b_price:.2f}, date={b_idx.date()}")
            else:
                diff = b_rsi - rsi
                if diff >= 8:
                    st.success(f"B ยืนยัน! B = {b_price:.2f}, ว่าที่ C = {close:.2f}, date={idx.date()}")
                    break

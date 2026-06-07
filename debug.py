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

st.title("Debug Scanner")

sym = st.selectbox("เลือกหุ้น", ["HUMAN.BK", "CPALL.BK"])
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

    st.write(f"**Window start:** {window.index[0].date()}")
    st.write(f"**ATL date:** {atl_idx.date()}, price: {atl_price:.2f}, RSI: {atl_rsi:.1f}")

    atl_pos = df.index.get_loc(atl_idx)
    after_atl = df.iloc[atl_pos + 1:]
    st.write(f"**after_atl:** {len(after_atl)} rows, from {after_atl.index[0].date()} to {after_atl.index[-1].date()}")

    hua_price = None
    hua_rsi = None
    hua_idx = None
    found = False

    for idx, row in after_atl.iterrows():
        close = float(row["Close"])
        rsi_val = row["RSI"]
        if pd.isna(rsi_val): continue
        rsi = float(rsi_val)
        diff = rsi - atl_rsi
        if diff >= 8:
            if hua_price is None or close > hua_price:
                hua_price = close
                hua_rsi = rsi
                hua_idx = idx
                found = True
        else:
            if found and close > hua_price:
                hua_price = close
                hua_rsi = rsi
                hua_idx = idx

    st.write(f"**Hua candidate found:** {found}")
    if found:
        st.write(f"**Hua candidate:** date={hua_idx.date()}, price={hua_price:.2f}, RSI={hua_rsi:.1f}")

        after_hua = df.iloc[df.index.get_loc(hua_idx) + 1:]
        post_low_price = None
        post_low_idx = None
        confirmed = False
        confirm_idx = None

        for idx, row in after_hua.iterrows():
            close = float(row["Close"])
            rsi_val = row["RSI"]
            if pd.isna(rsi_val): continue
            rsi = float(rsi_val)

            if close < atl_price:
                st.error(f"CANCELLED at {idx.date()} close={close:.2f} < atl={atl_price:.2f}")
                break

            if post_low_price is None or close < post_low_price:
                post_low_price = close
                post_low_idx = idx

            diff = hua_rsi - rsi
            if diff >= 8:
                confirmed = True
                confirm_idx = idx
                st.success(f"Hua CONFIRMED at {idx.date()}, RSI diff={diff:.1f}")
                break

            if close > hua_price:
                st.warning(f"Breakout BEFORE hua confirm at {idx.date()} close={close:.2f}")
                confirmed = True
                confirm_idx = idx
                break

        if confirmed:
            after_confirm = df.iloc[df.index.get_loc(confirm_idx) + 1:]
            for idx, row in after_confirm.iterrows():
                close = float(row["Close"])
                if close < atl_price:
                    st.error(f"CANCELLED after confirm at {idx.date()}")
                    break
                if post_low_price is None or close < post_low_price:
                    post_low_price = close
                    post_low_idx = idx
                if close > hua_price:
                    today = df.index[-1]
                    days = (today - idx).days
                    st.success(f"BREAKOUT at {idx.date()}, close={close:.2f}, days ago={days}")
                    if post_low_idx:
                        st.write(f"Tood2: {post_low_idx.date()}, price={post_low_price:.2f}")
                    break
        else:
            st.error("Hua NOT confirmed — หา RSI Diff >= 8 ไม่ได้ก่อน Breakout")

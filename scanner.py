import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta


def calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def fetch_data(symbol: str, lookback_days: int = 270) -> pd.DataFrame:
    end = datetime.today()
    start = end - timedelta(days=lookback_days)
    df = yf.download(symbol, start=start, end=end,
                     auto_adjust=False, progress=False)
    if df.empty:
        return pd.DataFrame()
    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.dropna(inplace=True)
    df["RSI"] = calc_rsi(df["Close"])
    return df


def detect_pattern(df: pd.DataFrame, scan_days: int = 90) -> dict:
    result = {
        "state": "no_pattern",
        "tood1_idx": None, "tood1_price": None, "tood1_rsi": None,
        "hua_idx": None, "hua_price": None, "hua_rsi": None,
        "tood2_idx": None, "tood2_price": None,
        "tood2_candidate_price": None, "tood2_candidate_idx": None,
        "breakout_idx": None, "breakout_price": None,
        "pending_rsi_diff": None,
        "pct_from_hua": None,
        "days_since_break": None,
        "priority_group": None,
        "volume_lv": None,
        "max_vol_in_formation": None,
        "avg_vol_20": None,
    }

    # Step 1: ATL ใน scan_days window เท่านั้น
    window = df.iloc[-scan_days:]
    if len(window) < 20:
        return result

    atl_idx = window["Close"].idxmin()
    atl_price = float(df.loc[atl_idx, "Close"])
    atl_rsi = float(df.loc[atl_idx, "RSI"])

    if pd.isna(atl_rsi):
        return result

    # Step 2: ไล่ขวาจาก ATL หา หัว candidate
    # ใช้ iloc เพื่อไล่ขวาจาก ATL เท่านั้น ไม่ดึงข้อมูลก่อน ATL มาด้วย
    atl_pos = df.index.get_loc(atl_idx)
    after_atl = df.iloc[atl_pos + 1:]

    hua_candidate_price = None
    hua_candidate_rsi = None
    hua_candidate_idx = None
    hua_candidate_found = False

    for idx, row in after_atl.iterrows():
        close = float(row["Close"])
        rsi_val = row["RSI"]
        if pd.isna(rsi_val):
            continue
        rsi = float(rsi_val)
        rsi_diff_from_atl = rsi - atl_rsi

        if rsi_diff_from_atl >= 8:
            if hua_candidate_price is None or close > hua_candidate_price:
                hua_candidate_price = close
                hua_candidate_rsi = rsi
                hua_candidate_idx = idx
                hua_candidate_found = True
        else:
            if hua_candidate_found and close > hua_candidate_price:
                hua_candidate_price = close
                hua_candidate_rsi = rsi
                hua_candidate_idx = idx

    if not hua_candidate_found:
        return {**result, "state": "searching"}

    # Step 3: รอราคาย่อลงจน RSI Diff (หัว - ย่อ) >= 8
    after_hua_candidate = df.loc[hua_candidate_idx:].iloc[1:]

    hua_confirmed = False
    hua_confirm_idx = None
    post_hua_low_price = None
    post_hua_low_idx = None

    for idx, row in after_hua_candidate.iterrows():
        close = float(row["Close"])
        rsi_val = row["RSI"]
        if pd.isna(rsi_val):
            continue
        rsi = float(rsi_val)

        if close < atl_price:
            return {**result, "state": "cancelled"}

        if post_hua_low_price is None or close < post_hua_low_price:
            post_hua_low_price = close
            post_hua_low_idx = idx

        rsi_diff_from_hua = hua_candidate_rsi - rsi
        if rsi_diff_from_hua >= 8:
            hua_confirmed = True
            hua_confirm_idx = idx
            break

        if close > hua_candidate_price:
            break

    if not hua_confirmed:
        return {**result, "state": "searching"}

    result["tood1_idx"] = atl_idx
    result["tood1_price"] = atl_price
    result["tood1_rsi"] = atl_rsi
    result["hua_idx"] = hua_candidate_idx
    result["hua_price"] = hua_candidate_price
    result["hua_rsi"] = hua_candidate_rsi
    result["state"] = "hua"

    # Step 4: หลังคอนเฟิมหัว ติดตาม ว่าที่ตูด 2
    # KEY FIX: ขยับ Low ใหม่เสมอ แม้ RSI Diff >= 8 แล้ว
    after_confirm = df.loc[hua_confirm_idx:].iloc[1:]

    for idx, row in after_confirm.iterrows():
        close = float(row["Close"])
        rsi_val = row["RSI"]
        if pd.isna(rsi_val):
            continue

        if close < atl_price:
            return {**result, "state": "cancelled"}

        # อัปเดต ว่าที่ตูด 2 เสมอ ถ้าเจอ Low ใหม่
        if post_hua_low_price is None or close < post_hua_low_price:
            post_hua_low_price = close
            post_hua_low_idx = idx

        # Breakout คอนเฟิม
        if close > hua_candidate_price:
            result["tood2_idx"] = post_hua_low_idx
            result["tood2_price"] = post_hua_low_price
            result["tood2_candidate_price"] = post_hua_low_price
            result["tood2_candidate_idx"] = post_hua_low_idx
            result["breakout_idx"] = idx
            result["breakout_price"] = close
            result["state"] = "confirmed"
            today = df.index[-1]
            result["days_since_break"] = (today - idx).days
            d = result["days_since_break"]
            if d <= 2:
                result["priority_group"] = "break_lv4"
            elif d <= 5:
                result["priority_group"] = "break_lv3"
            elif d <= 10:
                result["priority_group"] = "break_lv2"
            else:
                result["priority_group"] = "break_lv1"
            break

    # จ่อ Break
    if result["state"] == "hua":
        latest = df.iloc[-1]
        latest_close = float(latest["Close"])

        # RSI Diff วัดจาก หัว ถึง ว่าที่ตูด 2 (Low ต่ำสุดหลังหัว)
        tood2_rsi = None
        if post_hua_low_idx is not None:
            rsi_val = df.loc[post_hua_low_idx, "RSI"]
            if not pd.isna(rsi_val):
                tood2_rsi = float(rsi_val)

        pending_diff = (hua_candidate_rsi - tood2_rsi) if tood2_rsi is not None else 0

        result["tood2_candidate_price"] = post_hua_low_price
        result["tood2_candidate_idx"] = post_hua_low_idx
        result["pending_rsi_diff"] = round(pending_diff, 2)
        result["pct_from_hua"] = round(
            (hua_candidate_price - latest_close) / hua_candidate_price * 100, 2
        )

        if pending_diff >= 8 and result["pct_from_hua"] <= 3:
            result["priority_group"] = 4
        elif pending_diff >= 8:
            result["priority_group"] = 3
        elif pending_diff >= 4:
            result["priority_group"] = 2
        else:
            result["priority_group"] = 1

        result["state"] = "จ่อ_break"

    # Volume Analysis
    if result["tood1_idx"] is not None:
        end_vol = result["breakout_idx"] if result["breakout_idx"] else df.index[-1]
        try:
            form_vol = df.loc[result["tood1_idx"]:end_vol, "Volume"]
            max_vol = float(form_vol.max())
        except Exception:
            max_vol = np.nan

        avg_20 = float(df["Volume"].iloc[-20:].mean())
        ath_vol_1y = float(df["Volume"].iloc[-252:].max()) if len(df) >= 252 else float(df["Volume"].max())

        result["max_vol_in_formation"] = max_vol
        result["avg_vol_20"] = avg_20

        if pd.notna(max_vol) and avg_20 > 0:
            ratio = max_vol / avg_20
            if max_vol >= ath_vol_1y:
                result["volume_lv"] = "LV4"
            elif ratio >= 5:
                result["volume_lv"] = "LV3"
            elif ratio >= 1.5:
                result["volume_lv"] = "LV2"
            else:
                result["volume_lv"] = "LV1"
        else:
            result["volume_lv"] = "LV1"

    return result


def detect_nested(df: pd.DataFrame, scan_days: int = 90) -> dict:
    result_gen1 = detect_pattern(df, scan_days)
    result_gen1["generation"] = 1

    if result_gen1.get("state") == "confirmed" and result_gen1.get("tood2_idx") is not None:
        tood2_pos = df.index.get_loc(result_gen1["tood2_idx"])
        df_gen2 = df.iloc[tood2_pos:]
        days_remaining = len(df_gen2)
        if days_remaining >= 20:
            result_gen2 = detect_pattern(df_gen2, scan_days=days_remaining)
            result_gen2["generation"] = 2
            result_gen2["parent"] = result_gen1
            if result_gen2.get("state") not in ("no_pattern", "cancelled", "searching"):
                return result_gen2

    return result_gen1


def scan_universe(symbols: list, scan_days: int = 90) -> list:
    results = []
    for sym in symbols:
        try:
            df = fetch_data(sym, lookback_days=scan_days + 180)
            if df.empty or len(df) < 30:
                continue
            state = detect_nested(df, scan_days=scan_days)
            if state.get("state") in ("no_pattern", "searching", "cancelled", "no_data"):
                continue
            state["symbol"] = sym
            state["latest_close"] = round(float(df["Close"].iloc[-1]), 2)
            state["scan_date"] = df.index[-1].strftime("%Y-%m-%d")
            results.append(state)
        except Exception as e:
            print(f"Error {sym}: {e}")
            continue

    vol_order = {"LV4": 0, "LV3": 1, "LV2": 2, "LV1": 3, None: 4}
    group_order = {4: 0, 3: 1, 2: 2, 1: 3,
                   "break_lv4": 4, "break_lv3": 5,
                   "break_lv2": 6, "break_lv1": 7}

    def sort_key(r):
        pg = group_order.get(r.get("priority_group"), 99)
        vl = vol_order.get(r.get("volume_lv"), 4)
        pct = r.get("pct_from_hua") or 999
        return (pg, vl, pct)

    results.sort(key=sort_key)
    return results

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta


# ─── RSI Calculation ────────────────────────────────────────────────────────

def calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


# ─── Fetch Price Data ────────────────────────────────────────────────────────

def fetch_data(symbol: str, lookback_days: int = 180) -> pd.DataFrame:
    """
    Fetch OHLCV data using yfinance.
    We fetch 180 days so RSI has enough warm-up period before the 90-day window.
    """
    end = datetime.today()
    start = end - timedelta(days=lookback_days)
    df = yf.download(symbol, start=start, end=end,
                     auto_adjust=False, progress=False)
    if df.empty:
        return pd.DataFrame()
    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.dropna(inplace=True)
    df["RSI"] = calc_rsi(df["Close"])
    return df


# ─── Find ATL in 90-day window ───────────────────────────────────────────────

def find_atl_90(df: pd.DataFrame) -> int | None:
    """
    Return the index position (iloc) of the lowest Close in the last 90 days.
    This is the starting point (ตูด 1 candidate).
    """
    window = df.iloc[-90:]
    if window.empty:
        return None
    return window["Close"].idxmin()


# ─── Core Pattern Detection ──────────────────────────────────────────────────

def detect_pattern(df: pd.DataFrame, start_idx_label) -> dict:
    """
    Given a DataFrame and the label-index of ตูด 1,
    scan forward to detect ตูด1 → หัว → (ตูด2 / จ่อ Break).

    Returns a state dict describing the current pattern status.
    """
    if start_idx_label not in df.index:
        return {"state": "no_pattern"}

    start_pos = df.index.get_loc(start_idx_label)
    scan = df.iloc[start_pos:]

    state = {
        "state": "searching",       # searching | tood1 | hua | จ่อ_break | confirmed
        "tood1_idx": None,
        "tood1_price": None,
        "tood1_rsi": None,
        "hua_idx": None,
        "hua_price": None,
        "hua_rsi": None,
        "tood2_idx": None,
        "tood2_price": None,
        "tood2_confirm_idx": None,
        "breakout_idx": None,
        "breakout_price": None,
        "pending_low_idx": None,    # Low after หัว, waiting for confirm
        "pending_low_price": None,
        "pending_low_rsi": None,
        "pending_rsi_diff": None,
        "pct_from_hua": None,
        "days_since_break": None,
        "priority_group": None,     # 1-4 for จ่อ Break, "break_lv1-4" for Break
        "volume_lv": None,
        "max_vol_in_formation": None,
        "avg_vol_20": None,
    }

    # ─── Step 1: Find ตูด 1 ──────────────────────────────────────────────
    # ATL is given; scan forward until RSI Diff (current close RSI - ATL RSI) >= 8

    atl_rsi = scan["RSI"].iloc[0]
    atl_price = scan["Close"].iloc[0]
    atl_idx = scan.index[0]

    tood1_found = False
    tood1_confirm_pos = None

    for i in range(1, len(scan)):
        row = scan.iloc[i]
        if pd.isna(row["RSI"]):
            continue
        diff = row["RSI"] - atl_rsi
        if diff >= 8:
            # ตูด 1 confirmed at ATL, signalled on day i
            state["tood1_idx"] = atl_idx
            state["tood1_price"] = atl_price
            state["tood1_rsi"] = atl_rsi
            tood1_found = True
            tood1_confirm_pos = i
            break

    if not tood1_found:
        return {**state, "state": "searching"}

    state["state"] = "tood1"

    # ─── Step 2: Find หัว ────────────────────────────────────────────────
    # After ตูด 1 confirmed, scan forward for a Peak then a pullback
    # where RSI Diff (peak RSI - current RSI) >= 8
    # หัว price must be > ตูด 1 price

    scan2 = scan.iloc[tood1_confirm_pos:]
    peak_rsi = scan2["RSI"].iloc[0]
    peak_price = scan2["Close"].iloc[0]
    peak_idx = scan2.index[0]

    hua_found = False
    hua_confirm_pos_in_scan2 = None

    for i in range(1, len(scan2)):
        row = scan2.iloc[i]
        if pd.isna(row["RSI"]):
            continue

        # Update rolling peak
        if row["RSI"] > peak_rsi:
            peak_rsi = row["RSI"]
            peak_price = row["Close"]
            peak_idx = row.name

        # Check: pullback from peak, RSI Diff >= 8, peak must be > tood1
        diff = peak_rsi - row["RSI"]
        if diff >= 8 and peak_price > state["tood1_price"]:
            state["hua_idx"] = peak_idx
            state["hua_price"] = peak_price
            state["hua_rsi"] = peak_rsi
            hua_found = True
            hua_confirm_pos_in_scan2 = i
            break

        # ล้างไพ่: ราคาปิดต่ำกว่าตูด 1
        if row["Close"] < state["tood1_price"]:
            return {**state, "state": "cancelled"}

    if not hua_found:
        return {**state, "state": "tood1"}

    state["state"] = "hua"

    # ─── Step 3: Scan after หัว ──────────────────────────────────────────
    # Two outcomes:
    #   A) ราคาปิด < ตูด 1  → ล้างไพ่
    #   B) ราคาปิด > หัว    → Breakout confirmed → ตูด 2 = lowest close between หัว and breakout

    hua_abs_pos = scan.index.get_loc(state["hua_idx"])
    scan3_start = hua_confirm_pos_in_scan2  # relative to scan2
    scan3 = scan2.iloc[scan3_start:]

    tood1_price = state["tood1_price"]
    hua_price = state["hua_price"]
    hua_rsi = state["hua_rsi"]

    # Track lowest Low between หัว and breakout (potential ตูด 2)
    post_hua_low_price = None
    post_hua_low_rsi = None
    post_hua_low_idx = None

    for i in range(len(scan3)):
        row = scan3.iloc[i]
        if pd.isna(row["RSI"]):
            continue

        close = row["Close"]
        idx = row.name

        # ล้างไพ่
        if close < tood1_price:
            return {**state, "state": "cancelled"}

        # Update post-หัว low
        if post_hua_low_price is None or close < post_hua_low_price:
            post_hua_low_price = close
            post_hua_low_rsi = row["RSI"]
            post_hua_low_idx = idx

        # Check RSI Diff for post-หัว low
        if post_hua_low_rsi is not None:
            post_diff = hua_rsi - post_hua_low_rsi
        else:
            post_diff = 0

        # Breakout confirmed
        if close > hua_price:
            state["tood2_idx"] = post_hua_low_idx
            state["tood2_price"] = post_hua_low_price
            state["tood2_confirm_idx"] = idx
            state["breakout_idx"] = idx
            state["breakout_price"] = close
            today = df.index[-1]
            state["days_since_break"] = (today - idx).days
            state["state"] = "confirmed"

            # Assign break LV
            d = state["days_since_break"]
            if d <= 2:
                state["priority_group"] = "break_lv4"
            elif d <= 5:
                state["priority_group"] = "break_lv3"
            elif d <= 10:
                state["priority_group"] = "break_lv2"
            else:
                state["priority_group"] = "break_lv1"
            break

    # ─── Still waiting (จ่อ Break) ──────────────────────────────────────
    if state["state"] == "hua":
        state["pending_low_idx"] = post_hua_low_idx
        state["pending_low_price"] = post_hua_low_price
        state["pending_low_rsi"] = post_hua_low_rsi
        state["pending_rsi_diff"] = (hua_rsi - post_hua_low_rsi) if post_hua_low_rsi else 0

        latest_close = df["Close"].iloc[-1]
        state["pct_from_hua"] = round(
            (hua_price - latest_close) / hua_price * 100, 2
        ) if hua_price else None

        # Assign priority group
        rsi_diff = state["pending_rsi_diff"] or 0
        if rsi_diff >= 8 and state["pct_from_hua"] is not None and state["pct_from_hua"] <= 3:
            state["priority_group"] = 4
        elif rsi_diff >= 8:
            state["priority_group"] = 3
        elif rsi_diff >= 4:
            state["priority_group"] = 2
        else:
            state["priority_group"] = 1

        state["state"] = "จ่อ_break"

    # ─── Volume Analysis ─────────────────────────────────────────────────
    if state["tood1_idx"] is not None:
        end_vol_idx = state["breakout_idx"] if state["breakout_idx"] else df.index[-1]
        try:
            form_slice = df.loc[state["tood1_idx"]:end_vol_idx, "Volume"]
            max_vol = form_slice.max()
        except Exception:
            max_vol = np.nan

        # Average volume 20 days
        avg_20 = df["Volume"].iloc[-20:].mean()
        state["max_vol_in_formation"] = max_vol
        state["avg_vol_20"] = avg_20

        # ATH Volume in 1 year
        ath_vol_1y = df["Volume"].iloc[-252:].max() if len(df) >= 252 else df["Volume"].max()

        if pd.notna(max_vol) and pd.notna(avg_20) and avg_20 > 0:
            ratio = max_vol / avg_20
            if max_vol >= ath_vol_1y:
                state["volume_lv"] = "LV4"
            elif ratio >= 5:
                state["volume_lv"] = "LV3"
            elif ratio >= 1.5:
                state["volume_lv"] = "LV2"
            else:
                state["volume_lv"] = "LV1"
        else:
            state["volume_lv"] = "LV1"

    return state


# ─── Nested Structure (Matryoshka) ───────────────────────────────────────────

def detect_nested(df: pd.DataFrame) -> dict:
    """
    After a confirmed breakout (gen 1),
    use ตูด 2 of gen1 as ตูด 1 of gen2 and run detection again.
    Returns the most advanced state found.
    """
    atl_idx = find_atl_90(df)
    if atl_idx is None:
        return {"state": "no_data", "generation": 0}

    result_gen1 = detect_pattern(df, atl_idx)
    result_gen1["generation"] = 1

    if result_gen1.get("state") == "confirmed" and result_gen1.get("tood2_idx") is not None:
        result_gen2 = detect_pattern(df, result_gen1["tood2_idx"])
        result_gen2["generation"] = 2
        result_gen2["parent"] = result_gen1
        return result_gen2

    return result_gen1


# ─── Scan Universe ───────────────────────────────────────────────────────────

def scan_universe(symbols: list[str]) -> list[dict]:
    """
    Scan a list of symbols and return sorted results.
    """
    results = []
    for sym in symbols:
        try:
            df = fetch_data(sym)
            if df.empty or len(df) < 30:
                continue
            state = detect_nested(df)
            if state.get("state") in ("no_pattern", "searching", "cancelled", "no_data"):
                continue
            state["symbol"] = sym
            state["latest_close"] = round(df["Close"].iloc[-1], 2)
            state["scan_date"] = df.index[-1].strftime("%Y-%m-%d")
            results.append(state)
        except Exception as e:
            print(f"Error scanning {sym}: {e}")
            continue

    # ─── Sort results ──────────────────────────────────────────────────
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

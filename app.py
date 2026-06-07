import streamlit as st
import pandas as pd
from scanner import scan_universe

st.set_page_config(
    page_title="ตูด หัว ตูด Scanner",
    page_icon="📊",
    layout="wide",
)

# ─── Sidebar ─────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("📊 ตูด หัว ตูด")
    st.caption("ระบบ ViVi Investor — THREE CAP")
    st.divider()

    symbols_input = st.text_area(
        "รายชื่อหุ้น (คั่นด้วยบรรทัดใหม่)",
        value="PTT.BK\nADVANC.BK\nKBANK.BK\nSCC.BK\nCPALL.BK",
        height=200,
    )

    min_priority = st.selectbox(
        "แสดงกลุ่มขั้นต่ำ (จ่อ Break)",
        options=[1, 2, 3, 4],
        index=0,
        format_func=lambda x: f"กลุ่ม {x}+",
    )

    show_break_lv = st.multiselect(
        "แสดง Break LV (Break แล้ว)",
        options=["LV4", "LV3", "LV2", "LV1"],
        default=["LV4", "LV3", "LV2", "LV1"],
    )

    run_btn = st.button("🔍 สแกนเลย!", use_container_width=True, type="primary")

# ─── Helper: Badge HTML ───────────────────────────────────────────────────────

def priority_badge(pg):
    color_map = {
        4: ("#fff3cd", "#856404", "กลุ่ม 4 🔥🔥🔥🔥"),
        3: ("#fde8d8", "#7d3200", "กลุ่ม 3 🔥🔥🔥"),
        2: ("#e8f4fd", "#0c4a7c", "กลุ่ม 2 🔥🔥"),
        1: ("#f0f0f0", "#444441", "กลุ่ม 1 🔥"),
        "break_lv4": ("#d1f7c4", "#1a5c02", "Break LV4 ✅✅✅✅"),
        "break_lv3": ("#d1f7c4", "#1a5c02", "Break LV3 ✅✅✅"),
        "break_lv2": ("#d1f7c4", "#1a5c02", "Break LV2 ✅✅"),
        "break_lv1": ("#e8f0e8", "#3b6d11", "Break LV1 ✅"),
    }
    bg, fg, label = color_map.get(pg, ("#f0f0f0", "#444", str(pg)))
    return f'{label}'


def vol_badge(lv):
    color_map = {
        "LV4": ("#ffe8e8", "#7d0000", "🔥🔥🔥🔥 LV4"),
        "LV3": ("#fde8d8", "#7d3200", "🔥🔥🔥 LV3"),
        "LV2": ("#fff3cd", "#856404", "🔥🔥 LV2"),
        "LV1": ("#f0f0f0", "#444441", "🔥 LV1"),
    }
    bg, fg, label = color_map.get(lv, ("#f0f0f0", "#444", str(lv)))
    return f'{label}'


def state_badge(s):
    label_map = {
        "จ่อ_break": ("🟡", "จ่อ Break"),
        "confirmed": ("🟢", "Break แล้ว"),
        "hua": ("🔵", "มีหัวแล้ว"),
        "tood1": ("⚪", "มีตูด1"),
    }
    icon, label = label_map.get(s, ("⚫", s))
    return f"{icon} {label}"


# ─── Build Table Row ──────────────────────────────────────────────────────────

def build_row(r):
    sym = r.get("symbol", "")
    state = r.get("state", "")
    pg = r.get("priority_group")
    vl = r.get("volume_lv", "LV1")
    gen = r.get("generation", 1)
    latest = r.get("latest_close", "-")
    hua_price = r.get("hua_price")
    pct = r.get("pct_from_hua")
    days = r.get("days_since_break")
    rsi_diff = r.get("pending_rsi_diff")

    pct_str = f"{pct:.1f}%" if pct is not None else "-"
    days_str = f"{days} วัน" if days is not None else "-"
    hua_str = f"{hua_price:.2f}" if hua_price else "-"
    rsi_str = f"{rsi_diff:.1f}" if rsi_diff is not None else "-"
    gen_str = f"Gen {gen}" if gen > 1 else ""

    return {
        "หุ้น": f"{sym} {gen_str}",
        "สถานะ": state_badge(state),
        "Priority": priority_badge(pg),
        "Volume": vol_badge(vl),
        "ราคาล่าสุด": latest,
        "ราคาหัว": hua_str,
        "ห่างหัว %": pct_str,
        "RSI Diff": rsi_str,
        "Break มาแล้ว": days_str,
    }


# ─── Main ─────────────────────────────────────────────────────────────────────

st.title("📊 ตูด หัว ตูด Scanner")
st.caption("ระบบ ViVi Investor by THREE CAP | สแกนหาหุ้น Beginning of Trend ตาม Dow Theory + RSI Divergence")
st.divider()

if run_btn:
    symbols = [s.strip().upper() for s in symbols_input.splitlines() if s.strip()]
    if not symbols:
        st.warning("กรุณาใส่รายชื่อหุ้นก่อนครับ")
        st.stop()

    with st.spinner(f"กำลังสแกน {len(symbols)} ตัว..."):
        results = scan_universe(symbols)

    if not results:
        st.info("ไม่พบหุ้นที่ผ่านเงื่อนไขในขณะนี้")
        st.stop()

    # ─── Split tabs ──────────────────────────────────────────────────────
    waiting = [r for r in results
               if r.get("state") == "จ่อ_break"
               and (r.get("priority_group") or 0) >= min_priority]

    confirmed = [r for r in results
                 if r.get("state") == "confirmed"
                 and r.get("priority_group", "").replace("break_", "").upper() in show_break_lv]

    tab1, tab2 = st.tabs([
        f"🟡 จ่อ Break ({len(waiting)} ตัว)",
        f"🟢 Break แล้ว ({len(confirmed)} ตัว)",
    ])

    with tab1:
        if waiting:
            rows = [build_row(r) for r in waiting]
            df_show = pd.DataFrame(rows)
            st.write(
                df_show.to_html(escape=False, index=False),
                unsafe_allow_html=True,
            )
            st.caption(f"แสดง {len(waiting)} ตัว | เรียงลำดับ: Priority กลุ่ม → Volume LV → % ห่างหัว")
        else:
            st.info("ไม่มีหุ้นในกลุ่มจ่อ Break ที่ตรงเงื่อนไข")

    with tab2:
        if confirmed:
            rows = [build_row(r) for r in confirmed]
            df_show = pd.DataFrame(rows)
            st.write(
                df_show.to_html(escape=False, index=False),
                unsafe_allow_html=True,
            )
            st.caption(f"แสดง {len(confirmed)} ตัว | เรียงลำดับ: Break LV (วันน้อย = Priority สูง) → Volume LV")
        else:
            st.info("ไม่มีหุ้น Break แล้วในเงื่อนไขที่เลือก")

    # ─── Summary metrics ─────────────────────────────────────────────────
    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("สแกนทั้งหมด", f"{len(symbols)} ตัว")
    c2.metric("ผ่านเงื่อนไข", f"{len(results)} ตัว")
    c3.metric("🟡 จ่อ Break", f"{len(waiting)} ตัว")
    c4.metric("🟢 Break แล้ว", f"{len(confirmed)} ตัว")

else:
    st.info("👈 ใส่รายชื่อหุ้นใน Sidebar แล้วกด สแกนเลย!")

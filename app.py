import streamlit as st
import pandas as pd
from scanner import scan_universe

st.set_page_config(
    page_title="ตูด หัว ตูด Scanner",
    page_icon="📊",
    layout="wide",
)

SP500_SYMBOLS = []
SET100_SYMBOLS = []

try:
    sp500_df = pd.read_csv("sp500.csv")
    SP500_SYMBOLS = sp500_df.iloc[:, 0].dropna().str.strip().tolist()
except Exception:
    pass

try:
    set100_df = pd.read_csv("set100.csv")
    SET100_SYMBOLS = set100_df.iloc[:, 0].dropna().str.strip().tolist()
except Exception:
    pass

with st.sidebar:
    st.title("📊 ตูด หัว ตูด")
    st.caption("ระบบ ViVi Investor — VITALi")
    st.divider()

    st.subheader("เลือกรายชื่อหุ้น")
    input_mode = st.radio(
        "วิธีเลือก",
        options=["พิมพ์เอง", "S&P500", "SET100", "อัปโหลด CSV"],
        index=0,
        horizontal=False,
    )

    symbols = []

    if input_mode == "พิมพ์เอง":
        symbols_input = st.text_area(
            "ใส่ชื่อหุ้น (บรรทัดละตัว)",
            value="PTT.BK\nADVANC.BK\nKBANK.BK\nSCC.BK\nCPALL.BK\nHUMAN.BK",
            height=180,
        )
        symbols = [s.strip().upper() for s in symbols_input.splitlines() if s.strip()]

    elif input_mode == "S&P500":
        if SP500_SYMBOLS:
            st.success(f"โหลด S&P500 ได้ {len(SP500_SYMBOLS)} ตัว")
            symbols = SP500_SYMBOLS
        else:
            st.warning("ยังไม่มีไฟล์ sp500.csv — กรุณาอัปโหลดไฟล์ก่อน")

    elif input_mode == "SET100":
        if SET100_SYMBOLS:
            st.success(f"โหลด SET100 ได้ {len(SET100_SYMBOLS)} ตัว")
            symbols = SET100_SYMBOLS
        else:
            st.warning("ยังไม่มีไฟล์ set100.csv — กรุณาอัปโหลดไฟล์ก่อน")

    elif input_mode == "อัปโหลด CSV":
        uploaded = st.file_uploader("อัปโหลดไฟล์ CSV (คอลัมน์แรก = ชื่อหุ้น)", type=["csv"])
        if uploaded:
            try:
                uploaded_df = pd.read_csv(uploaded)
                symbols = uploaded_df.iloc[:, 0].dropna().str.strip().str.upper().tolist()
                st.success(f"โหลดได้ {len(symbols)} ตัว")
            except Exception as e:
                st.error(f"อ่านไฟล์ไม่ได้: {e}")

    st.divider()

    scan_days = st.slider(
        "ย้อนหลังกี่วัน (หา ATL)",
        min_value=30,
        max_value=180,
        value=90,
        step=10,
        help="Default 90 วัน ตามระบบ ViVi"
    )

    st.divider()

    st.subheader("กลุ่มจ่อ Breakout")
    st.caption("เลือกว่าจะดูหุ้นที่พร้อมแค่ไหน")
    readiness_min = st.selectbox(
        "แสดงตั้งแต่ระดับ",
        options=[1, 2, 3, 4],
        index=0,
        format_func=lambda x: {
            1: "1 — รอสัญญาณ (ทุกตัว)",
            2: "2 — เริ่มส่งสัญญาณ",
            3: "3 — สัญญาณชัด",
            4: "4 — จวนจะระเบิด 🔥",
        }[x]
    )

    st.divider()

    st.subheader("กลุ่ม Breakout แล้ว")
    st.caption("เลือกว่า Break มานานแค่ไหน")
    break_lv_show = st.multiselect(
        "เพิ่งทะลุมาไม่เกิน",
        options=["LV4", "LV3", "LV2", "LV1"],
        default=["LV4", "LV3", "LV2", "LV1"],
        format_func=lambda x: {
            "LV4": "LV4 — 1-2 วัน (ร้อนแรงที่สุด)",
            "LV3": "LV3 — 3-5 วัน",
            "LV2": "LV2 — 6-10 วัน",
            "LV1": "LV1 — 10 วันขึ้นไป",
        }[x]
    )

    st.divider()
    run_btn = st.button("🔍 สแกนเลย!", use_container_width=True, type="primary")


def priority_badge(pg):
    m = {
        4: ("#fff3cd","#856404","จวนจะระเบิด 🔥🔥🔥🔥"),
        3: ("#fde8d8","#7d3200","สัญญาณชัด 🔥🔥🔥"),
        2: ("#e8f4fd","#0c4a7c","เริ่มส่งสัญญาณ 🔥🔥"),
        1: ("#f0f0f0","#444441","รอสัญญาณ 🔥"),
        "break_lv4": ("#d1f7c4","#1a5c02","Break 1-2 วัน ✅✅✅✅"),
        "break_lv3": ("#d1f7c4","#1a5c02","Break 3-5 วัน ✅✅✅"),
        "break_lv2": ("#d1f7c4","#1a5c02","Break 6-10 วัน ✅✅"),
        "break_lv1": ("#e8f0e8","#3b6d11","Break 10+ วัน ✅"),
    }
    bg,fg,label = m.get(pg,("#f0f0f0","#444",str(pg)))
    return f'{label}'


def vol_badge(lv):
    m = {
        "LV4": ("#ffe8e8","#7d0000","Vol สูงสุดในรอบปี 🔥🔥🔥🔥"),
        "LV3": ("#fde8d8","#7d3200","Vol ผิดปกติมาก 🔥🔥🔥"),
        "LV2": ("#fff3cd","#856404","Vol ผิดปกติ 🔥🔥"),
        "LV1": ("#f0f0f0","#444441","Vol ปกติ"),
    }
    bg,fg,label = m.get(lv,("#f0f0f0","#444",str(lv)))
    return f'{label}'


def build_row(r):
    sym = r.get("symbol","")
    gen = r.get("generation",1)
    pg = r.get("priority_group")
    vl = r.get("volume_lv","LV1")
    latest = r.get("latest_close","-")
    hua = r.get("hua_price")
    pct = r.get("pct_from_hua")
    days = r.get("days_since_break")
    rdiff = r.get("pending_rsi_diff")

    return {
        "หุ้น": f"{sym}" + (f" Gen{gen}" if gen>1 else ""),
        "ระดับความพร้อม": priority_badge(pg),
        "Volume": vol_badge(vl),
        "ราคาล่าสุด": latest,
        "ราคาหัว": f"{hua:.2f}" if hua else "-",
        "ห่างหัว %": f"{pct:.1f}%" if pct is not None else "-",
        "RSI Diff": f"{rdiff:.1f}" if rdiff is not None else "-",
        "Break มาแล้ว": f"{days} วัน" if days is not None else "-",
    }


st.title("📊 ตูด หัว ตูด Scanner")
st.caption("ระบบ ViVi Investor — VITALi | สแกนหาหุ้น Beginning of Trend ตาม Dow Theory + RSI Diff 8")
st.divider()

if run_btn:
    if not symbols:
        st.warning("กรุณาเลือกหรือใส่รายชื่อหุ้นก่อนครับ")
        st.stop()

    with st.spinner(f"กำลังสแกน {len(symbols)} ตัว..."):
        results = scan_universe(symbols, scan_days=scan_days)

    if not results:
        st.info("ไม่พบหุ้นที่ผ่านเงื่อนไขในขณะนี้")
        st.stop()

    waiting = [r for r in results
               if r.get("state") == "จ่อ_break"
               and (r.get("priority_group") or 0) >= readiness_min]

    confirmed = [r for r in results
                 if r.get("state") == "confirmed"
                 and r.get("priority_group","").replace("break_","").upper() in break_lv_show]

    tab1, tab2 = st.tabs([
        f"🟡 จ่อ Breakout ({len(waiting)} ตัว)",
        f"🟢 Breakout แล้ว ({len(confirmed)} ตัว)",
    ])

    with tab1:
        if waiting:
            rows = [build_row(r) for r in waiting]
            st.write(pd.DataFrame(rows).to_html(escape=False,index=False), unsafe_allow_html=True)
            st.caption("เรียงลำดับ: ระดับความพร้อม → Volume → % ห่างหัว")
        else:
            st.info("ไม่มีหุ้นในกลุ่มจ่อ Breakout ที่ตรงเงื่อนไข")

    with tab2:
        if confirmed:
            rows = [build_row(r) for r in confirmed]
            st.write(pd.DataFrame(rows).to_html(escape=False,index=False), unsafe_allow_html=True)
            st.caption("เรียงลำดับ: วันที่ Break (น้อย = Priority สูง) → Volume")
        else:
            st.info("ไม่มีหุ้น Breakout แล้วในเงื่อนไขที่เลือก")

    st.divider()
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("สแกนทั้งหมด", f"{len(symbols)} ตัว")
    c2.metric("ผ่านเงื่อนไข", f"{len(results)} ตัว")
    c3.metric("🟡 จ่อ Breakout", f"{len(waiting)} ตัว")
    c4.metric("🟢 Breakout แล้ว", f"{len(confirmed)} ตัว")

else:
    st.info("👈 เลือกหุ้นใน Sidebar แล้วกด สแกนเลย!")

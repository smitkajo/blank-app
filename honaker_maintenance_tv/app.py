from datetime import datetime
from io import BytesIO

import pandas as pd
import streamlit as st

from maintenance_logic import process_due_list


ROTATE_SECONDS = 12
MAX_COMING_UP = 5

st.set_page_config(
    page_title="Maintenance TV Board",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      .block-container {padding-top: 1.0rem; padding-bottom: 1rem; max-width: 100%;}
      header[data-testid="stHeader"] {background: rgba(0,0,0,0);}
      [data-testid="stToolbar"] {visibility: hidden; height: 0%; position: fixed;}
      #MainMenu {visibility: hidden;}
      footer {visibility: hidden;}

      .topbar {
        display:flex; justify-content:space-between; align-items:end;
        border-bottom: 2px solid rgba(128,128,128,.35); padding-bottom: .45rem; margin-bottom: .8rem;
      }
      .brand {font-size: 1.15rem; font-weight: 800; letter-spacing: .16rem; opacity: .75;}
      .tail {font-size: 4.4rem; font-weight: 900; line-height: .95; margin: 0;}
      .model {font-size: 1.1rem; opacity:.7; text-align:right;}

      .hero {
        border: 2px solid rgba(128,128,128,.42); border-radius: 18px;
        padding: 1.1rem 1.4rem; margin: .8rem 0 1rem 0;
      }
      .hero-label {font-size: 1rem; font-weight:800; letter-spacing:.12rem; opacity:.66;}
      .hero-title {font-size: 2.2rem; font-weight: 900; line-height:1.1; margin:.25rem 0 .7rem 0;}
      .hero-remaining {font-size:3.1rem; font-weight:900; line-height:1;}
      .hero-meta {font-size:1.05rem; opacity:.72; margin-top:.65rem;}

      .section-title {font-size:1.05rem; font-weight:900; letter-spacing:.12rem; opacity:.68; margin:.25rem 0 .4rem 0;}
      .item {
        display:grid; grid-template-columns: 1.1fr 3.5fr 1.2fr;
        gap:1rem; align-items:center; padding:.64rem .85rem;
        border-top:1px solid rgba(128,128,128,.27);
      }
      .item:first-of-type {border-top: none;}
      .assembly {font-size:1.0rem; font-weight:800; opacity:.68;}
      .desc {font-size:1.28rem; font-weight:750; line-height:1.14;}
      .remain {font-size:1.35rem; font-weight:900; text-align:right;}
      .overdue {font-size:1.45rem; font-weight:950; text-align:right;}
      .footerline {font-size:.85rem; opacity:.55; text-align:right; padding-top:.5rem;}
      .empty {font-size:2rem; font-weight:800; opacity:.65; padding:4rem 1rem; text-align:center;}
    </style>
    """,
    unsafe_allow_html=True,
)


def load_workbook(file_bytes: bytes) -> pd.DataFrame:
    xls = pd.ExcelFile(BytesIO(file_bytes))
    sheet = "Task Export" if "Task Export" in xls.sheet_names else xls.sheet_names[0]
    return pd.read_excel(BytesIO(file_bytes), sheet_name=sheet)


def display_text(value):
    if pd.isna(value) or value is None:
        return ""
    return str(value).strip()


def html_escape(text):
    import html
    return html.escape(display_text(text))


with st.sidebar:
    st.title("Maintenance Board")
    uploaded = st.file_uploader("Upload Fleet Due List", type=["xlsx"], key="fleet_upload")
    st.caption("For this test version, keep this browser session open after uploading. The TV board will rotate automatically.")
    st.divider()
    st.write("**Display rules**")
    st.caption("Big inspections: controlling limit under 30 hours")
    st.caption("Coming up: ≤75 hrs, ≤30 days, or ≤75 landings/cycles")
    st.caption(f"Rotation: {ROTATE_SECONDS} seconds per aircraft")

if uploaded is not None:
    current_bytes = uploaded.getvalue()
    fingerprint = (uploaded.name, len(current_bytes), hash(current_bytes[:2048]))
    if st.session_state.get("upload_fingerprint") != fingerprint:
        try:
            raw = load_workbook(current_bytes)
            st.session_state["maintenance_df"] = process_due_list(raw)
            st.session_state["upload_name"] = uploaded.name
            st.session_state["loaded_at"] = datetime.now()
            st.session_state["upload_fingerprint"] = fingerprint
            st.session_state["rotation_index"] = 0
        except Exception as exc:
            st.error(f"Could not read this due list: {exc}")
            st.stop()

if "maintenance_df" not in st.session_state:
    st.title("Maintenance TV Board")
    st.info("Upload the latest Fleet Due List from the sidebar to start the board.")
    st.stop()


df = st.session_state["maintenance_df"]
active = df[df["Actionable"]].copy()

# Only rotate tails that currently have something useful for the shop to see.
tails = sorted(active["A/C Reg."].dropna().astype(str).unique().tolist())

if not tails:
    st.markdown('<div class="empty">No upcoming maintenance is inside the current TV thresholds.</div>', unsafe_allow_html=True)
    st.stop()

if "rotation_index" not in st.session_state:
    st.session_state["rotation_index"] = 0


@st.fragment(run_every=f"{ROTATE_SECONDS}s")
def rotating_board():
    # Advance after the first fragment run.
    runs = st.session_state.get("fragment_runs", 0)
    if runs > 0:
        st.session_state["rotation_index"] = (st.session_state["rotation_index"] + 1) % len(tails)
    st.session_state["fragment_runs"] = runs + 1

    idx = st.session_state["rotation_index"] % len(tails)
    tail = tails[idx]
    tail_df = active[active["A/C Reg."].astype(str) == tail].copy().sort_values("Urgency")

    model = display_text(tail_df["A/C Model"].dropna().iloc[0]) if "A/C Model" in tail_df and tail_df["A/C Model"].notna().any() else ""

    st.markdown(
        f"""
        <div class="topbar">
          <div>
            <div class="brand">HONAKER AVIATION • MAINTENANCE STATUS</div>
            <div class="tail">{html_escape(tail)}</div>
          </div>
          <div class="model">{html_escape(model)}<br>{idx+1} of {len(tails)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    big = tail_df[tail_df["Big Inspection <30 Hrs"]].sort_values("Urgency")
    if not big.empty:
        row = big.iloc[0]
        assembly = display_text(row.get("Major Assembly"))
        task_no = display_text(row.get("Task Number"))
        meta_bits = [x for x in [assembly, task_no] if x]
        meta = " • ".join(meta_bits)
        st.markdown(
            f"""
            <div class="hero">
              <div class="hero-label">NEXT BIG INSPECTION</div>
              <div class="hero-title">{html_escape(row.get('Description'))}</div>
              <div class="hero-remaining">{html_escape(row.get('Controlling Display'))}</div>
              <div class="hero-meta">{html_escape(meta)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    coming = tail_df.copy()
    if not big.empty:
        # Don't repeat the hero row immediately below it.
        coming = coming.drop(index=big.index[0], errors="ignore")
    coming = coming.head(MAX_COMING_UP)

    st.markdown('<div class="section-title">COMING UP</div>', unsafe_allow_html=True)
    if coming.empty:
        st.markdown('<div class="empty">No additional items inside the current display window.</div>', unsafe_allow_html=True)
    else:
        for _, row in coming.iterrows():
            assembly = display_text(row.get("Major Assembly")) or display_text(row.get("Task Type"))
            desc = display_text(row.get("Description"))
            rem = display_text(row.get("Controlling Display")) or display_text(row.get("Remaining Time"))
            overdue_class = "overdue" if "OVD" in display_text(row.get("Remaining Time")).upper() else "remain"
            st.markdown(
                f"""
                <div class="item">
                  <div class="assembly">{html_escape(assembly)}</div>
                  <div class="desc">{html_escape(desc)}</div>
                  <div class="{overdue_class}">{html_escape(rem)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    loaded_at = st.session_state.get("loaded_at")
    loaded_text = loaded_at.strftime("%b %d, %Y %I:%M %p") if loaded_at else ""
    st.markdown(
        f'<div class="footerline">Source: {html_escape(st.session_state.get("upload_name", ""))} • Loaded {html_escape(loaded_text)}</div>',
        unsafe_allow_html=True,
    )


rotating_board()

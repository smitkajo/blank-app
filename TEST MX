import re
import math
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Big Inspection Test Board", layout="wide")

st.title("Upcoming Big Inspections - Test Run")

uploaded_file = st.file_uploader(
    "Upload due list export",
    type=["xlsx", "csv"]
)

# ----------------------------
# LOAD DATA
# ----------------------------
def load_data(file):
    if file.name.lower().endswith(".csv"):
        df = pd.read_csv(file)
    else:
        df = pd.read_excel(file, sheet_name="Task Export")
    return df


# ----------------------------
# HELPERS
# ----------------------------
def clean_text(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def to_lower(value):
    return clean_text(value).lower()


def parse_remaining_time(remaining_text):
    """
    Parses strings like:
      '5 Days (+30), 736.3 Hrs (+30)'
      '29.5 Hrs (+100)'
      '22 Days (+15)'
      '5 Hrs'
      '0 Hrs (+75.2)'

    Returns a list of dicts like:
    [
      {"raw": "5 Days (+30)", "unit": "Days", "value": 5.0, "tolerance": 30.0},
      {"raw": "736.3 Hrs (+30)", "unit": "Hrs", "value": 736.3, "tolerance": 30.0}
    ]
    """
    text = clean_text(remaining_text)
    if not text:
        return []

    parts = [p.strip() for p in text.split(",") if p.strip()]
    parsed = []

    pattern = re.compile(
        r"(?P<value>-?\d+(?:\.\d+)?)\s*(?P<unit>Days?|Hrs?|Hours?|Mos?|Months?|Enc|Cycles?|Ldg)\s*(?:\(\+(?P<tolerance>\d+(?:\.\d+)?)\))?",
        re.IGNORECASE
    )

    for part in parts:
        match = pattern.search(part)
        if match:
            value = float(match.group("value"))
            unit = match.group("unit").strip()
            tolerance = match.group("tolerance")
            parsed.append(
                {
                    "raw": part,
                    "value": value,
                    "unit": unit,
                    "tolerance": float(tolerance) if tolerance else None,
                }
            )

    return parsed


def normalize_unit(unit):
    u = unit.lower()
    if "hr" in u or "hour" in u:
        return "Hrs"
    if "day" in u:
        return "Days"
    if "mo" in u:
        return "Months"
    if "enc" in u:
        return "Enc"
    if "cycle" in u:
        return "Cycles"
    if "ldg" in u:
        return "Landings"
    return unit


def get_first_coming_trigger(remaining_text):
    """
    If there are two or more time remainings, use whichever comes first.
    For mixed units, this test version prioritizes in this order:
      1. overdue/zero items first
      2. smallest hour trigger
      3. smallest day trigger
      4. smallest month trigger
      5. other smallest numeric trigger

    This gives you a consistent rule for display.

    Returns:
      {
        "display": "5 Hrs (+30)",
        "value": 5.0,
        "unit": "Hrs",
        "tolerance": 30.0
      }
    """
    parsed = parse_remaining_time(remaining_text)
    if not parsed:
        return {
            "display": "",
            "value": None,
            "unit": None,
            "tolerance": None
        }

    normalized = []
    for item in parsed:
        normalized.append(
            {
                "raw": item["raw"],
                "value": item["value"],
                "unit": normalize_unit(item["unit"]),
                "tolerance": item["tolerance"]
            }
        )

    # anything overdue or already due should come first
    due_now = [x for x in normalized if x["value"] <= 0]
    if due_now:
        chosen = sorted(due_now, key=lambda x: x["value"])[0]
    else:
        hours = [x for x in normalized if x["unit"] == "Hrs"]
        days = [x for x in normalized if x["unit"] == "Days"]
        months = [x for x in normalized if x["unit"] == "Months"]
        others = [x for x in normalized if x["unit"] not in {"Hrs", "Days", "Months"}]

        if hours:
            chosen = sorted(hours, key=lambda x: x["value"])[0]
        elif days:
            chosen = sorted(days, key=lambda x: x["value"])[0]
        elif months:
            chosen = sorted(months, key=lambda x: x["value"])[0]
        else:
            chosen = sorted(others, key=lambda x: x["value"])[0]

    tolerance_text = ""
    if chosen["tolerance"] is not None:
        tol = int(chosen["tolerance"]) if float(chosen["tolerance"]).is_integer() else chosen["tolerance"]
        tolerance_text = f" (+{tol})"

    value_text = int(chosen["value"]) if float(chosen["value"]).is_integer() else chosen["value"]

    return {
        "display": f"{value_text} {chosen['unit']}{tolerance_text}",
        "value": chosen["value"],
        "unit": chosen["unit"],
        "tolerance": chosen["tolerance"]
    }


def is_big_inspection(row):
    """
    Test-run rule for 'BIG inspections':
    Includes inspection/package items that look like major inspection events.

    You can tighten or loosen this later.
    """
    task_type = to_lower(row.get("Task Type"))
    task_category = to_lower(row.get("Task Category"))
    description = to_lower(row.get("Description"))
    active_req = to_lower(row.get("Active Requirement"))

    big_keywords = [
        "inspection document",
        "routine periodic inspection",
        "phase inspection",
        "major inspection",
        "continuous inspection"
    ]

    looks_big = any(word in description for word in big_keywords)
    package_or_inspection = task_type in {"package", "inspection"}

    # This keeps big packaged inspection items
    return package_or_inspection and (
        looks_big
        or "continuous inspection" in task_category
        or "inspection" in description
    )


def is_completed(row):
    status = to_lower(row.get("Compliance Status"))
    closed_words = {"completed", "complied", "closed", "done"}
    return status in closed_words


def add_logic_columns(df):
    df = df.copy()

    df["First Coming Trigger"] = df["Remaining Time"].apply(get_first_coming_trigger)
    df["Trigger Display"] = df["First Coming Trigger"].apply(lambda x: x["display"])
    df["Trigger Value"] = df["First Coming Trigger"].apply(lambda x: x["value"])
    df["Trigger Unit"] = df["First Coming Trigger"].apply(lambda x: x["unit"])
    df["Trigger Tolerance"] = df["First Coming Trigger"].apply(lambda x: x["tolerance"])

    df["Big Inspection"] = df.apply(is_big_inspection, axis=1)
    df["Completed"] = df.apply(is_completed, axis=1)

    # Show in upcoming big inspections only if BIG inspection and the first-coming trigger is Hrs < 30
    df["Show Upcoming Big Inspection"] = (
        (df["Big Inspection"] == True)
        & (df["Completed"] == False)
        & (df["Trigger Unit"] == "Hrs")
        & (df["Trigger Value"].notna())
        & (df["Trigger Value"] < 30)
    )

    # try to make date columns usable
    if "Next Due Date" in df.columns:
        df["Next Due Date Parsed"] = pd.to_datetime(df["Next Due Date"], errors="coerce")
    else:
        df["Next Due Date Parsed"] = pd.NaT

    return df


def make_display_table(df):
    columns = [
        "A/C Reg.",
        "Task Type",
        "Task Category",
        "Description",
        "Active Requirement",
        "Remaining Time",
        "Trigger Display",
        "Next Due Date",
        "Estimated Due Date",
        "WP/WO",
    ]

    existing = [c for c in columns if c in df.columns]
    display_df = df[existing].copy()

    if "Description" in display_df.columns:
        display_df["Description"] = display_df["Description"].astype(str).str.replace("\n", " ", regex=False)

    return display_df


# ----------------------------
# MAIN APP
# ----------------------------
if uploaded_file is not None:
    df = load_data(uploaded_file)

    required_cols = ["A/C Reg.", "Task Type", "Task Category", "Description", "Remaining Time"]
    missing = [c for c in required_cols if c not in df.columns]

    if missing:
        st.error(f"Missing expected columns: {', '.join(missing)}")
        st.stop()

    df = add_logic_columns(df)

    st.subheader("Quick Summary")
    total_rows = len(df)
    big_count = int(df["Big Inspection"].sum())
    upcoming_big_count = int(df["Show Upcoming Big Inspection"].sum())

    c1, c2, c3 = st.columns(3)
    c1.metric("Rows in Upload", total_rows)
    c2.metric("Big Inspection Rows", big_count)
    c3.metric("Upcoming Big Inspections (<30 Hrs)", upcoming_big_count)

    upcoming_big = df[df["Show Upcoming Big Inspection"]].copy()

    if not upcoming_big.empty:
        upcoming_big = upcoming_big.sort_values(
            by=["Trigger Value", "Next Due Date Parsed"],
            ascending=[True, True]
        )

    st.subheader("Upcoming Big Inspections")
    st.caption("Only BIG inspections where the first-coming trigger is an hour-based remaining time below 30 hours. Tolerance is shown in parentheses.")

    if upcoming_big.empty:
        st.info("No big inspections found under 30 hours in this upload.")
    else:
        st.dataframe(
            make_display_table(upcoming_big),
            use_container_width=True,
            hide_index=True
        )

        st.subheader("Scrolling Card View")
        for _, row in upcoming_big.iterrows():
            with st.container(border=True):
                st.markdown(f"### {row.get('A/C Reg.', '')} - {row.get('Description', '')}")
                col1, col2, col3 = st.columns(3)
                col1.write(f"**Task Type:** {clean_text(row.get('Task Type'))}")
                col2.write(f"**Category:** {clean_text(row.get('Task Category'))}")
                col3.write(f"**First Trigger:** {clean_text(row.get('Trigger Display'))}")

                col4, col5 = st.columns(2)
                col4.write(f"**Active Requirement:** {clean_text(row.get('Active Requirement'))}")
                col5.write(f"**Next Due Date:** {clean_text(row.get('Next Due Date')) or clean_text(row.get('Estimated Due Date'))}")

                if clean_text(row.get("WP/WO")):
                    st.write(f"**WP/WO:** {clean_text(row.get('WP/WO'))}")

    with st.expander("See parsed trigger logic"):
        preview_cols = [
            "Description",
            "Remaining Time",
            "Trigger Display",
            "Trigger Unit",
            "Trigger Value",
            "Trigger Tolerance",
            "Big Inspection",
            "Show Upcoming Big Inspection"
        ]
        preview_cols = [c for c in preview_cols if c in df.columns]
        st.dataframe(df[preview_cols], use_container_width=True, hide_index=True)

else:
    st.info("Upload a due list export to test the big inspection filter.")

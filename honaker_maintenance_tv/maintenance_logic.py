import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List

import pandas as pd


CLOSED_STATUSES = {"completed", "complied", "closed", "done", "cancelled", "canceled"}

BIG_INSPECTION_KEYWORDS = (
    "routine periodic inspection",
    "inspection document",
    "inspection phase",
    "phase inspection",
    "major inspection",
)

# TV thresholds. Easy to change later.
COMING_UP_HOURS = 75.0
COMING_UP_DAYS = 30.0
COMING_UP_COUNTER = 75.0
BIG_INSPECTION_HOURS = 30.0


@dataclass
class Limit:
    raw: str
    value: float
    unit: str
    tolerance_value: Optional[float] = None
    tolerance_unit: Optional[str] = None


def clean(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def normalize_unit(unit: str) -> str:
    u = clean(unit).lower()
    if u in {"hr", "hrs", "hour", "hours"}:
        return "Hrs"
    if u in {"day", "days"}:
        return "Days"
    if u in {"month", "months", "mos", "mo"}:
        return "Months"
    if u in {"enc", "encs"}:
        return "Enc"
    if u in {"ldg", "ldgs", "landing", "landings"}:
        return "Ldg"
    if u in {"apus", "apu"}:
        return "APUS"
    if u in {"cycles", "cycle", "cyc"}:
        return "Cycles"
    return clean(unit)


def parse_clock_hours(value: str) -> float:
    """Traxxall-style 28:30 Hrs = 28.5 hours."""
    value = clean(value)
    if ":" in value:
        left, right = value.split(":", 1)
        return float(left) + float(right) / 60.0
    return float(value)


def parse_tolerance(text: Optional[str], default_unit: str):
    if not text:
        return None, None
    s = clean(text).lstrip("+").strip()
    # Examples: 350, 36:24, 31 Days
    m = re.match(r"(?P<num>-?\d+(?:\.\d+)?(?::\d+)?)\s*(?P<unit>[A-Za-z]+)?", s)
    if not m:
        return None, None
    num = m.group("num")
    unit = normalize_unit(m.group("unit") or default_unit)
    try:
        val = parse_clock_hours(num) if unit == "Hrs" else float(num)
    except ValueError:
        return None, unit
    return val, unit


def parse_remaining_time(text) -> List[Limit]:
    s = clean(text)
    if not s or s.upper() == "OVD":
        return []

    limits: List[Limit] = []
    for piece in [p.strip() for p in s.split(",") if p.strip()]:
        if piece.upper() == "OVD":
            continue

        m = re.search(
            r"(?P<value>-?\d+(?:\.\d+)?(?::\d+)?)\s*"
            r"(?P<unit>Hrs?|Hours?|Days?|Months?|Mos?|Enc|Ldg|Landings?|APUS?|Cycles?)"
            r"(?:\s*\(\+(?P<tol>[^)]+)\))?",
            piece,
            flags=re.IGNORECASE,
        )
        if not m:
            continue

        unit = normalize_unit(m.group("unit"))
        raw_value = m.group("value")
        try:
            value = parse_clock_hours(raw_value) if unit == "Hrs" else float(raw_value)
        except ValueError:
            continue

        tol_value, tol_unit = parse_tolerance(m.group("tol"), unit)
        limits.append(
            Limit(
                raw=piece,
                value=value,
                unit=unit,
                tolerance_value=tol_value,
                tolerance_unit=tol_unit,
            )
        )
    return limits


def format_number(value: Optional[float]) -> str:
    if value is None:
        return ""
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.1f}".rstrip("0").rstrip(".")


def format_hours_as_traxxall(hours: float) -> str:
    total_minutes = round(hours * 60)
    h, m = divmod(total_minutes, 60)
    if m == 0:
        return f"{h} Hrs"
    return f"{h}:{m:02d} Hrs"


def format_limit(limit: Limit, include_tolerance=True) -> str:
    if limit.unit == "Hrs":
        base = format_hours_as_traxxall(limit.value)
    else:
        base = f"{format_number(limit.value)} {limit.unit}"

    if include_tolerance and limit.tolerance_value is not None:
        if limit.tolerance_unit == "Hrs":
            tol_num = format_hours_as_traxxall(limit.tolerance_value).replace(" Hrs", "")
            tol = tol_num
        else:
            tol = format_number(limit.tolerance_value)
            if limit.tolerance_unit and limit.tolerance_unit != limit.unit:
                tol += f" {limit.tolerance_unit}"
        base += f" (+{tol})"
    return base


def best_limit_for_unit(limits: List[Limit], unit: str) -> Optional[Limit]:
    same = [x for x in limits if x.unit == unit]
    return min(same, key=lambda x: x.value) if same else None


def select_controlling_limit(row) -> Optional[Limit]:
    """
    Best-effort 'whatever comes first' logic.

    When both calendar and utilization limits exist, Traxxall gives us:
      - Next Due Date (calendar)
      - Estimated Due Date (projected utilization)
    We compare those dates and display the corresponding remaining limit.
    """
    remaining = clean(row.get("Remaining Time"))
    if "OVD" in remaining.upper():
        return Limit(raw="OVD", value=-1, unit="OVD")

    limits = parse_remaining_time(remaining)
    if not limits:
        return None
    if len(limits) == 1:
        return limits[0]

    calendar = next((x for x in limits if x.unit in {"Days", "Months"}), None)
    utilization = next((x for x in limits if x.unit in {"Hrs", "Enc", "Ldg", "Cycles", "APUS"}), None)

    next_due = pd.to_datetime(row.get("Next Due Date"), errors="coerce")
    estimated_due = pd.to_datetime(row.get("Estimated Due Date"), errors="coerce")

    if calendar and utilization and pd.notna(next_due) and pd.notna(estimated_due):
        return calendar if next_due <= estimated_due else utilization

    # If only one projected date exists, map it to the corresponding type.
    if calendar and pd.notna(next_due) and pd.isna(estimated_due):
        return calendar
    if utilization and pd.notna(estimated_due) and pd.isna(next_due):
        return utilization

    # We cannot safely convert days/months to hours without a utilization forecast.
    # Keep the export order rather than pretending those units are directly comparable.
    return limits[0]


def is_closed(row) -> bool:
    status = clean(row.get("Compliance Status")).lower()
    return status in CLOSED_STATUSES


def is_big_inspection(row) -> bool:
    task_type = clean(row.get("Task Type")).lower()
    description = clean(row.get("Description")).lower()
    category = clean(row.get("Task Category")).lower()
    task_number = clean(row.get("Task Number")).lower()

    if task_type not in {"package", "inspection"}:
        return False

    text = " ".join([description, category, task_number])
    return any(k in text for k in BIG_INSPECTION_KEYWORDS) or "continuous inspection program" in category


def big_inspection_under_30(row) -> bool:
    if not is_big_inspection(row):
        return False
    control = select_controlling_limit(row)
    return bool(control and control.unit == "Hrs" and 0 <= control.value < BIG_INSPECTION_HOURS)


def is_actionable(row) -> bool:
    remaining = clean(row.get("Remaining Time"))
    if not remaining:
        return False
    if "OVD" in remaining.upper():
        return True

    control = select_controlling_limit(row)
    if not control:
        return False

    if control.unit == "Hrs":
        return control.value <= COMING_UP_HOURS
    if control.unit in {"Days", "Months"}:
        if control.unit == "Days":
            return control.value <= COMING_UP_DAYS
        return control.value <= 1.0
    if control.unit in {"Enc", "Ldg", "Cycles", "APUS"}:
        return control.value <= COMING_UP_COUNTER
    return False


def urgency_score(row) -> float:
    remaining = clean(row.get("Remaining Time"))
    if "OVD" in remaining.upper():
        return -100000

    control = select_controlling_limit(row)
    if not control:
        return 999999

    if control.unit == "Hrs":
        return control.value
    if control.unit == "Days":
        return control.value * 4
    if control.unit == "Months":
        return control.value * 120
    if control.unit in {"Enc", "Ldg", "Cycles", "APUS"}:
        return control.value * 1.5
    return 999999


def process_due_list(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    if "A/C Reg." not in df.columns or "Remaining Time" not in df.columns:
        raise ValueError("This does not look like the expected Fleet Due List export.")

    df = df[df["A/C Reg."].notna()].copy()
    df = df[~df.apply(is_closed, axis=1)].copy()

    df["Controlling Limit"] = df.apply(select_controlling_limit, axis=1)
    df["Controlling Display"] = df["Controlling Limit"].apply(
        lambda x: "OVD" if x and x.unit == "OVD" else (format_limit(x) if x else "")
    )
    df["Is Big Inspection"] = df.apply(is_big_inspection, axis=1)
    df["Big Inspection <30 Hrs"] = df.apply(big_inspection_under_30, axis=1)
    df["Actionable"] = df.apply(is_actionable, axis=1)
    df["Urgency"] = df.apply(urgency_score, axis=1)

    # Exact duplicate rows occasionally occur in exports. Keep meaningful assembly differences.
    dedupe_cols = [
        c for c in ["A/C Reg.", "Major Assembly", "Task Number", "Description", "Remaining Time"]
        if c in df.columns
    ]
    if dedupe_cols:
        df = df.drop_duplicates(subset=dedupe_cols, keep="first")

    return df

"""
season_utils.py
================
Tells the dashboard which "season" a date falls into, and how
to display that season as a colored banner.

Seasons:
  kharif      -> Oct 1 - Nov 30  (main paddy stubble-burning season)
  rabi        -> Apr 1 - May 31  (wheat stubble-burning season)
  pre_season  -> Sep 1 - Sep 30  (lead-up to kharif)
  off_season  -> everything else (Jun-Aug, Dec-Mar)
"""

from datetime import date

KHARIF_MONTHS     = [10, 11]
RABI_MONTHS       = [4, 5]
PRE_SEASON_MONTHS = [9]

SEASON_INFO = {
    "kharif":     {"label": "Kharif (Paddy) Season",  "color": "red"},
    "rabi":       {"label": "Rabi (Wheat) Season",    "color": "orange"},
    "pre_season": {"label": "Pre-Season (September)", "color": "amber"},
    "off_season": {"label": "Monitoring Mode",        "color": "grey"},
}

BANNER_COLORS = {
    "red":    {"bg": "#FEE2E2", "border": "#fca5a5", "text": "#991B1B"},
    "orange": {"bg": "#FFEDD5", "border": "#fdba74", "text": "#9a3412"},
    "amber":  {"bg": "#FEF3C7", "border": "#fcd34d", "text": "#92400E"},
    "grey":   {"bg": "#F3F4F6", "border": "#d1d5db", "text": "#374151"},
}


def get_season_state(check_date=None):
    d = check_date or date.today()
    m = d.month

    if m in KHARIF_MONTHS:
        days_in = (m - 10) * 30 + d.day  # Day 1 = Oct 1
        info = SEASON_INFO["kharif"]
        return {"state": "kharif", "label": info["label"], "color": info["color"],
                "active": True, "days_in": days_in, "days_to_next": 0}

    if m in RABI_MONTHS:
        info = SEASON_INFO["rabi"]
        return {"state": "rabi", "label": info["label"], "color": info["color"],
                "active": True, "days_in": None, "days_to_next": 0}

    if m in PRE_SEASON_MONTHS:
        info = SEASON_INFO["pre_season"]
        days_to_next = (date(d.year, 10, 1) - d).days
        return {"state": "pre_season", "label": info["label"], "color": info["color"],
                "active": False, "days_in": None, "days_to_next": days_to_next}

    info = SEASON_INFO["off_season"]
    next_year = d.year if m < 10 else d.year + 1
    days_to_next = (date(next_year, 10, 1) - d).days
    return {"state": "off_season", "label": info["label"], "color": info["color"],
            "active": False, "days_in": None, "days_to_next": days_to_next}


def get_banner_text(season):
    if season["state"] == "kharif":
        return f"🚨 KHARIF SEASON ACTIVE — Day {season['days_in']} of 61 | Predictions updated daily"
    if season["state"] == "rabi":
        return "🌱 RABI SEASON ACTIVE — Wheat straw burning period | Secondary risk monitoring"
    if season["state"] == "pre_season":
        return (f"⏳ PRE-SEASON ALERT — Kharif burning season begins in "
                f"{season['days_to_next']} days | System preparing")
    return (f"📊 MONITORING MODE — No active burning season | "
            f"Next season in {season['days_to_next']} days")


def render_season_banner(season):
    colors = BANNER_COLORS[season["color"]]
    text = get_banner_text(season)
    return f"""
    <div style="
        background:{colors['bg']};
        border:1px solid {colors['border']};
        color:{colors['text']};
        border-radius:10px;
        padding:10px 18px;
        font-family:Inter,sans-serif;
        font-size:13px;
        font-weight:600;
        margin-bottom:18px;
    ">
        {text}
    </div>
    """
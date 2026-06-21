"""
model/seasonal_predictor.py
Season-aware wrapper around the FarmBreath AI risk model.

Implements the three-gate alert system:
  Gate 1 — Season check   (is it an active burning window?)
  Gate 2 — Confidence check (is the model confident enough?)
  Gate 3 — Risk threshold check (is the score above the user threshold?)

The dashboard imports get_season_state() at startup to decide which
dashboard state to render (active / pre_season / off_season).
predict_with_season_guard() is called when the user clicks Generate
Predictions; it respects all three gates before returning an alert.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional


# ══════════════════════════════════════════════════════════════════════════════
# SEASON WINDOWS
# ══════════════════════════════════════════════════════════════════════════════

SEASON_WINDOWS: dict[str, dict] = {
    "kharif": {
        "months": [10, 11],
        "label":  "Kharif (Paddy) Season",
        "color":  "red",
        "total_days": 61,           # Oct 1 – Nov 30
        "start_month": 10,
        "start_day":   1,
    },
    "rabi": {
        "months": [4, 5],
        "label":  "Rabi (Wheat) Season",
        "color":  "orange",
        "total_days": 61,           # Apr 1 – May 31
        "start_month": 4,
        "start_day":   1,
    },
    "pre_season": {
        "months": [9],
        "label":  "Pre-Season (September)",
        "color":  "amber",
        "total_days": 30,
        "start_month": 9,
        "start_day":   1,
    },
}

# Months with no active burning and no pre-season activity
OFF_SEASON_MONTHS = [1, 2, 3, 6, 7, 8, 12]


# ══════════════════════════════════════════════════════════════════════════════
# CORE SEASON STATE FUNCTION
# ══════════════════════════════════════════════════════════════════════════════

def get_season_state(check_date: Optional[date] = None) -> dict:
    """
    Return the current season state as a dict. Called once at dashboard startup.

    Returns
    -------
    dict with keys:
        state       : 'kharif' | 'rabi' | 'pre_season' | 'off_season'
        label       : Human-readable season name
        color       : 'red' | 'orange' | 'amber' | 'grey'
        active      : bool — True if predictions should run
        days_in     : int | None — days into current season (active seasons only)
        total_days  : int | None — total days in this season
        days_to_next: int | None — days until next kharif season (off-season only)
        days_to_kharif: int | None — days until kharif (pre_season only)
        banner_text : str — exact text for the season status banner
        footer_text : str — exact text for the dashboard footer
        map_title   : str — title to use above the risk map
    """
    d = check_date or date.today()
    m = d.month

    # ── Active and pre-season windows ─────────────────────────────────────────
    for season_key, cfg in SEASON_WINDOWS.items():
        if m in cfg["months"]:
            season_start = date(d.year, cfg["start_month"], cfg["start_day"])
            days_in = (d - season_start).days + 1

            # Days until next kharif (only relevant for pre-season)
            next_kharif = date(d.year, 10, 1)
            days_to_kharif = (next_kharif - d).days

            if season_key == "kharif":
                banner = (
                    f"🔴 KHARIF SEASON ACTIVE — Day {days_in} of {cfg['total_days']}"
                    f" | Predictions updated daily"
                )
                footer = (
                    "Model accuracy: 73.7% | Trained on 2021–2025 NASA FIRMS data"
                    " | 60 districts"
                )
                map_title = "Live District Risk Map — Next 7 Days | Data: NASA FIRMS + Open-Meteo"

            elif season_key == "rabi":
                banner = (
                    "🟠 RABI SEASON ACTIVE — Wheat straw burning period"
                    " | Secondary risk monitoring"
                )
                footer = (
                    "Rabi season model active | This is a secondary burning season"
                    " | Kharif season resumes October"
                )
                map_title = "Rabi Season Risk Map — Punjab & Haryana | April–May"

            else:  # pre_season
                banner = (
                    f"🟡 PRE-SEASON ALERT — Kharif burning season begins in"
                    f" {days_to_kharif} days | System preparing"
                )
                footer = (
                    "Pre-season mode active | Live predictions begin October 1"
                    " | Historical risk shown"
                )
                map_title = "Predicted High-Risk Districts — Based on Last Season Patterns"

            return {
                "state":           season_key,
                "label":           cfg["label"],
                "color":           cfg["color"],
                "active":          season_key in ("kharif", "rabi"),
                "days_in":         days_in,
                "total_days":      cfg["total_days"],
                "days_to_next":    None,
                "days_to_kharif":  days_to_kharif if season_key == "pre_season" else None,
                "banner_text":     banner,
                "footer_text":     footer,
                "map_title":       map_title,
            }

    # ── Off-season ────────────────────────────────────────────────────────────
    next_oct = date(d.year if m < 10 else d.year + 1, 10, 1)
    days_to_next = (next_oct - d).days

    return {
        "state":           "off_season",
        "label":           "Monitoring Mode",
        "color":           "grey",
        "active":          False,
        "days_in":         None,
        "total_days":      None,
        "days_to_next":    days_to_next,
        "days_to_kharif":  days_to_next,
        "banner_text": (
            f"⚫ MONITORING MODE — No active burning season"
            f" | Next season: {days_to_next} days"
        ),
        "footer_text": (
            "Prediction engine paused | Historical data shown"
            " | System will auto-activate October 1"
        ),
        "map_title": "Last Season Summary — 2024 Kharif Burning Incidents",
    }


# ══════════════════════════════════════════════════════════════════════════════
# THREE-GATE ALERT SYSTEM
# ══════════════════════════════════════════════════════════════════════════════

def apply_three_gates(
    district: str,
    risk_label: str,
    risk_score: float,
    confidence: float,
    season: dict,
    user_threshold: float = 5.0,
) -> dict:
    """
    Run all three gates and return a structured alert result.

    Gate 1 — Season check
    Gate 2 — Confidence check
    Gate 3 — Risk threshold check

    Parameters
    ----------
    district        : district name (title-cased for display)
    risk_label      : 'high' | 'medium' | 'low'
    risk_score      : 0–10 numeric score
    confidence      : model max class probability (0–1)
    season          : result of get_season_state()
    user_threshold  : sidebar slider value (default 5)

    Returns
    -------
    dict with keys:
        show_alert   : bool
        alert_level  : 'high' | 'medium' | 'low' | 'suppressed'
        alert_icon   : emoji
        alert_color  : hex background
        alert_border : hex border
        alert_text_color: hex
        alert_message: HTML string for st.markdown
        confidence_label: str
    """

    # ── GATE 1: Season check ──────────────────────────────────────────────────
    if not season["active"]:
        return _suppressed_alert(
            f"Off-season. Predictions paused."
            f" Next kharif season in {season['days_to_next']} days."
        )

    # ── GATE 2: Confidence check ──────────────────────────────────────────────
    if confidence < 0.55:
        conf_label = "⚠️ Low Confidence"
        return _suppressed_alert(
            f"Insufficient signal for {district} — model confidence"
            f" {confidence:.0%} is below the 55% minimum threshold."
        )
    elif confidence <= 0.70:
        conf_label = "🟡 Medium Confidence"
    else:
        conf_label = "✅ High Confidence"

    # ── GATE 3: Risk threshold check ─────────────────────────────────────────
    if risk_score < user_threshold:
        return {
            "show_alert":        True,
            "alert_level":       "below_threshold",
            "alert_icon":        "ℹ️",
            "alert_color":       "#F0F9FF",
            "alert_border":      "#BAE6FD",
            "alert_text_color":  "#0C4A6E",
            "confidence_label":  conf_label,
            "alert_message": (
                f"<b>{district}</b> risk score ({risk_score:.1f}) is below your"
                f" threshold of {user_threshold}. No intervention needed. [{conf_label}]"
            ),
        }

    # ── All gates passed — emit risk-level alert ──────────────────────────────
    if risk_score > 7:
        return {
            "show_alert":        True,
            "alert_level":       "high",
            "alert_icon":        "🔴",
            "alert_color":       "#FEE2E2",
            "alert_border":      "#fca5a5",
            "alert_text_color":  "#991B1B",
            "confidence_label":  conf_label,
            "alert_message": (
                f"<b>INTERVENTION REQUIRED:</b> {district} predicted at"
                f" <b>HIGH RISK</b> (score {risk_score:.1f}/10)."
                f" Deploy field teams for awareness. [{conf_label}]"
            ),
        }
    elif risk_score >= 4:
        return {
            "show_alert":        True,
            "alert_level":       "medium",
            "alert_icon":        "🟠",
            "alert_color":       "#FEF3C7",
            "alert_border":      "#fcd34d",
            "alert_text_color":  "#92400E",
            "confidence_label":  conf_label,
            "alert_message": (
                f"<b>MONITORING REQUIRED:</b> {district} shows"
                f" <b>MEDIUM RISK</b> (score {risk_score:.1f}/10)."
                f" Prepare response resources. [{conf_label}]"
            ),
        }
    else:
        return {
            "show_alert":        True,
            "alert_level":       "low",
            "alert_icon":        "🟢",
            "alert_color":       "#D1FAE5",
            "alert_border":      "#6ee7b7",
            "alert_text_color":  "#065F46",
            "confidence_label":  conf_label,
            "alert_message": (
                f"<b>LOW RISK:</b> {district} appears safe"
                f" (score {risk_score:.1f}/10). Normal conditions expected. [{conf_label}]"
            ),
        }


def _suppressed_alert(message: str) -> dict:
    return {
        "show_alert":        False,
        "alert_level":       "suppressed",
        "alert_icon":        "⚫",
        "alert_color":       "#F3F4F6",
        "alert_border":      "#D1D5DB",
        "alert_text_color":  "#6B7280",
        "confidence_label":  "N/A",
        "alert_message":     message,
    }


# ══════════════════════════════════════════════════════════════════════════════
# OPTIONAL: FULL MODEL WRAPPER (uses joblib if model file exists)
# ══════════════════════════════════════════════════════════════════════════════

def predict_with_season_guard(
    district_name: str,
    month: int,
    year: int,
    model_path: str = "model/risk_predictor.pkl",
    user_threshold: float = 5.0,
) -> dict:
    """
    Full three-gate prediction. Falls back gracefully if model file is absent.
    In the dashboard, simulated scores from current_predictions.csv are used
    directly — this function is the hook for real ML integration.
    """
    season = get_season_state(date(year, month, 1))

    if not season["active"]:
        return {
            "district":     district_name,
            "season_state": "off_season",
            "risk_label":   "NO PREDICTION",
            "risk_score":   None,
            "confidence":   None,
            "message":      season["banner_text"],
            "show_map":     "historical",
        }

    try:
        import joblib  # type: ignore
        model = joblib.load(model_path)
        # NOTE: replace _build_features with your actual feature engineering
        features = _build_features(district_name, month, year)
        proba = model.predict_proba([features])[0]
        confidence = float(max(proba))
        pred_class = str(model.classes_[proba.argmax()])
        risk_score = round(confidence * 10, 2)
    except (ImportError, FileNotFoundError):
        # Model not yet available — caller should use CSV-based scores instead
        return {
            "district":     district_name,
            "season_state": season["state"],
            "risk_label":   "UNAVAILABLE",
            "risk_score":   None,
            "confidence":   None,
            "message":      "ML model file not found. Using CSV-based predictions.",
            "show_map":     "csv",
        }

    alert = apply_three_gates(
        district_name, pred_class, risk_score, confidence, season, user_threshold
    )

    return {
        "district":        district_name,
        "season_state":    season["state"],
        "risk_label":      pred_class,
        "risk_score":      risk_score,
        "confidence":      confidence,
        "confidence_label": alert["confidence_label"],
        "alert":           alert,
        "show_map":        "live",
    }


def _build_features(district_name: str, month: int, year: int) -> list:
    """
    Placeholder feature builder. Replace with your actual feature engineering.
    """
    raise NotImplementedError(
        "Replace _build_features() with your actual feature engineering pipeline."
    )
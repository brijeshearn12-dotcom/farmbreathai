"""
predict.py  (FIXED)
====================
Key fixes vs previous version:
  1. lag_fire_count is now loaded per-district from master_dataset.csv
     (or district_lag_fire.csv if you pre-compute it). Hardcoding 50
     for every district gave every row an identical feature value,
     which is why all predictions collapsed to "medium".
  2. Calibrated thresholds loaded from model/class_thresholds.pkl
     (written by train_model.py). Instead of argmax(probability),
     we apply per-class thresholds so "high" and "low" districts are
     actually predicted as such.
  3. risk_score formula unchanged - still 0-10 scale.
  4. All other logic (geocoding, weather fetch, caching) unchanged.
"""

import os
import re
import sys
from datetime import datetime

import numpy as np
import pandas as pd
import requests
import joblib


# ---------------------------------------------------------------------
# Paths / endpoints
# ---------------------------------------------------------------------
MODEL_PATH = "model/risk_predictor.pkl"
THRESHOLDS_PATH = "model/class_thresholds.pkl"   # FIX 2
DISTRICTS_PATH = "data/districts.csv"
MASTER_DATA_PATH = "data/master_dataset.csv"     # FIX 1: for lag_fire_count
OUTPUT_PATH = "data/current_predictions.csv"
COORDS_CACHE_PATH = "data/district_coordinates.csv"

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
FORECAST_DAYS = 7

LABEL_MAP = {"low": 0, "medium": 1, "high": 2}
INVERSE_LABEL_MAP = {v: k for k, v in LABEL_MAP.items()}

FALLBACK_WEATHER = {
    "temperature_2m_max": 30.0,
    "precipitation_sum": 5.0,
    "windspeed_10m_max": 10.0,
    "relative_humidity_2m_mean": 50.0,
}

MANUAL_COORDINATE_OVERRIDES = {
    "Fatehgarh Sahib": (30.64, 76.39),
    "Sri Muktsar Sahib": (30.47, 74.52),
    "Shahid Bhagat Singh Nagar": (31.12, 76.12),
    "Malerkotla": (30.53, 75.88),
    "Kanpur Dehat": (26.45, 79.99),
}


# ---------------------------------------------------------------------
# 1. Load trained model
# ---------------------------------------------------------------------
if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(
        f"Could not find trained model at '{MODEL_PATH}'. "
        f"Run model/train_model.py first."
    )

model = joblib.load(MODEL_PATH)

if hasattr(model, "feature_names_in_"):
    FEATURE_COLUMNS = list(model.feature_names_in_)
else:
    FEATURE_COLUMNS = [
        "temperature_2m_max", "precipitation_sum", "windspeed_10m_max",
        "relative_humidity_2m_mean", "is_kharif_season", "is_rabi_season",
        "wind_drought_index", "lag_fire_count", "month",
        "month_sin", "month_cos",
    ]
    print("  [warning] model has no 'feature_names_in_'; using default feature list.")

print(f"Model expects {len(FEATURE_COLUMNS)} features: {FEATURE_COLUMNS}")

_CLASS_INDEX = {cls: idx for idx, cls in enumerate(model.classes_)}


# ---------------------------------------------------------------------
# FIX 2: Load calibrated thresholds (written by train_model.py)
# Falls back to simple argmax if the file doesn't exist yet.
# ---------------------------------------------------------------------
_THRESHOLDS = None
if os.path.exists(THRESHOLDS_PATH):
    _THRESHOLDS = joblib.load(THRESHOLDS_PATH)
    print(
        f"Loaded calibrated thresholds: "
        f"low>={_THRESHOLDS['low']:.2f}, high>={_THRESHOLDS['high']:.2f}"
    )
else:
    print(
        f"  [warning] No thresholds file at '{THRESHOLDS_PATH}'. "
        f"Using argmax (retrain to generate thresholds)."
    )


def predict_class_from_proba(proba):
    """Apply calibrated thresholds if available, else argmax."""
    if _THRESHOLDS is None:
        best_idx = int(np.argmax(proba))
        return int(model.classes_[best_idx]), float(proba[best_idx])

    co = _THRESHOLDS["class_order"]
    t_high = _THRESHOLDS["high"]
    t_low = _THRESHOLDS["low"]

    prob_high = proba[co.index(2)]
    prob_low = proba[co.index(0)]

    if prob_high >= t_high:
        predicted = 2
        confidence = prob_high
    elif prob_low >= t_low:
        predicted = 0
        confidence = prob_low
    else:
        predicted = 1
        confidence = proba[co.index(1)]

    return predicted, float(confidence)


# ---------------------------------------------------------------------
# 2. Load district list
# ---------------------------------------------------------------------
if not os.path.exists(DISTRICTS_PATH):
    raise FileNotFoundError(f"Could not find '{DISTRICTS_PATH}'.")

districts_df = pd.read_csv(DISTRICTS_PATH)

_possible_name_cols = [
    "district", "district_name", "District", "District_Name", "name", "DISTRICT",
]
district_col = next((c for c in _possible_name_cols if c in districts_df.columns), None)
if district_col is None:
    district_col = districts_df.columns[0]
    print(f"  [warning] No standard district-name column found; using '{district_col}'.")

district_names = districts_df[district_col].dropna().astype(str).unique().tolist()
print(f"Loaded {len(district_names)} districts from '{DISTRICTS_PATH}'.")


# ---------------------------------------------------------------------
# FIX 1: Build per-district lag_fire_count lookup from training data
# lag_fire_count is the MOST IMPORTANT feature for telling districts
# apart. Hardcoding it to 50 for every district was the main reason
# every prediction was "medium risk score 5".
# We take each district's MEAN lag_fire_count across all training rows.
# ---------------------------------------------------------------------
_lag_fire_lookup = {}
_DEFAULT_LAG_FIRE = 50   # fallback only if a district has no history

if os.path.exists(MASTER_DATA_PATH):
    try:
        master = pd.read_csv(MASTER_DATA_PATH)
        _dist_col_master = next(
            (c for c in ["nearest_district", "district", "District", "district_name"] if c in master.columns),
            None
        )
        if _dist_col_master and "lag_fire_count" in master.columns:
            _lag_fire_lookup = (
                master.groupby(_dist_col_master)["lag_fire_count"]
                .mean()
                .round(1)
                .to_dict()
            )
            print(
                f"Loaded lag_fire_count lookup for "
                f"{len(_lag_fire_lookup)} districts from master dataset."
            )
        else:
            print(
                "  [warning] Could not find district/lag_fire_count columns in "
                f"'{MASTER_DATA_PATH}'. Using fallback={_DEFAULT_LAG_FIRE}."
            )
    except Exception as exc:
        print(f"  [warning] Failed to load master dataset: {exc}")
else:
    print(
        f"  [warning] '{MASTER_DATA_PATH}' not found. "
        f"Using lag_fire_count={_DEFAULT_LAG_FIRE} for all districts."
    )


def get_lag_fire_count(district_name):
    """Return the mean historical lag_fire_count for this district."""
    if district_name in _lag_fire_lookup:
        return _lag_fire_lookup[district_name]
    # Try case-insensitive match
    lower = {k.lower(): v for k, v in _lag_fire_lookup.items()}
    v = lower.get(district_name.lower())
    if v is not None:
        return v
    return _DEFAULT_LAG_FIRE


# ---------------------------------------------------------------------
# 3. Coordinate cache + geocoding  (unchanged)
# ---------------------------------------------------------------------
_coordinate_cache = {}


def _load_coordinate_cache():
    if os.path.exists(COORDS_CACHE_PATH):
        cached = pd.read_csv(COORDS_CACHE_PATH)
        for _, row in cached.iterrows():
            if pd.notna(row["latitude"]) and pd.notna(row["longitude"]):
                _coordinate_cache[row["district"]] = (row["latitude"], row["longitude"])
        print(f"Loaded {len(_coordinate_cache)} cached district coordinates.")


def _save_coordinate_cache():
    if not _coordinate_cache:
        return
    rows = [{"district": k, "latitude": v[0], "longitude": v[1]} for k, v in _coordinate_cache.items()]
    out = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(COORDS_CACHE_PATH), exist_ok=True)
    out.to_csv(COORDS_CACHE_PATH, index=False)
    print(f"Saved coordinate cache ({len(out)} districts) to '{COORDS_CACHE_PATH}'.")


def geocode_district(district_name):
    candidates = [district_name]
    paren_match = re.search(r"\((.*?)\)", district_name)
    cleaned = re.sub(r"\(.*?\)", "", district_name).strip()
    if cleaned and cleaned != district_name and cleaned not in candidates:
        candidates.append(cleaned)
    if paren_match:
        alt = paren_match.group(1).strip()
        if alt and alt not in candidates:
            candidates.append(alt)

    for query in candidates:
        try:
            resp = requests.get(
                GEOCODING_URL,
                params={"name": query, "count": 5, "language": "en", "format": "json"},
                timeout=10,
            )
            data = resp.json()
            results = data.get("results") or []
            india_results = [r for r in results if r.get("country_code") == "IN"]
            chosen = india_results or results
            if chosen:
                r = chosen[0]
                return r["latitude"], r["longitude"]
        except Exception as exc:
            print(f"  [warning] Geocoding request failed for '{query}': {exc}")

    return None, None


def get_district_coordinates(district_name):
    if district_name in _coordinate_cache:
        return _coordinate_cache[district_name]
    if district_name in MANUAL_COORDINATE_OVERRIDES:
        coords = MANUAL_COORDINATE_OVERRIDES[district_name]
        _coordinate_cache[district_name] = coords
        return coords
    lat, lon = geocode_district(district_name)
    if lat is not None:
        _coordinate_cache[district_name] = (lat, lon)
    else:
        print(f"  [warning] Could not geocode '{district_name}'.")
    return lat, lon


# ---------------------------------------------------------------------
# 4. Live weather fetch  (unchanged)
# ---------------------------------------------------------------------
def fetch_live_weather(lat, lon):
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_max,precipitation_sum,windspeed_10m_max,relative_humidity_2m_mean",
        "forecast_days": FORECAST_DAYS,
        "timezone": "auto",
    }
    for attempt in range(2):
        try:
            resp = requests.get(FORECAST_URL, params=params, timeout=30)
            data = resp.json()
            if "daily" not in data:
                print(f"  [warning] Forecast API error: {data.get('reason', data)}")
                return None
            daily = data["daily"]
            return {
                "temperature_2m_max": float(np.nanmean(daily["temperature_2m_max"])),
                "precipitation_sum": float(np.nanmean(daily["precipitation_sum"])),
                "windspeed_10m_max": float(np.nanmean(daily["windspeed_10m_max"])),
                "relative_humidity_2m_mean": float(np.nanmean(daily["relative_humidity_2m_mean"])),
            }
        except requests.exceptions.Timeout:
            if attempt == 0:
                print("  [warning] Forecast request timed out, retrying...")
                continue
            print("  [warning] Forecast request timed out after retry.")
            return None
        except Exception as exc:
            print(f"  [warning] Forecast request failed: {exc}")
            return None
    return None


# ---------------------------------------------------------------------
# 5. Prediction function  (FIXED: lag_fire_count + calibrated thresholds)
# ---------------------------------------------------------------------
def predict_district_risk(district_name, month, year):
    lat, lon = get_district_coordinates(district_name)

    weather = None
    if lat is not None and lon is not None:
        weather = fetch_live_weather(lat, lon)

    if weather is None:
        print(f"  [warning] Using fallback weather values for '{district_name}'.")
        weather = FALLBACK_WEATHER.copy()

    is_kharif_season = 1 if month in [10, 11] else 0
    is_rabi_season = 1 if month in [4, 5] else 0

    # FIX 1: per-district lag_fire_count (not a hardcoded 50)
    lag_fire_count = get_lag_fire_count(district_name)

    wind_drought_index = (
        weather["windspeed_10m_max"]
        * (100 - weather["relative_humidity_2m_mean"])
        / (weather["precipitation_sum"] + 1)
    )

    month_sin = np.sin(2 * np.pi * month / 12)
    month_cos = np.cos(2 * np.pi * month / 12)

    all_features = {
        "temperature_2m_max": weather["temperature_2m_max"],
        "precipitation_sum": weather["precipitation_sum"],
        "windspeed_10m_max": weather["windspeed_10m_max"],
        "relative_humidity_2m_mean": weather["relative_humidity_2m_mean"],
        "is_kharif_season": is_kharif_season,
        "is_rabi_season": is_rabi_season,
        "wind_drought_index": wind_drought_index,
        "lag_fire_count": lag_fire_count,
        "month": month,
        "year": year,
        "month_sin": month_sin,
        "month_cos": month_cos,
    }

    row = pd.DataFrame([{col: all_features[col] for col in FEATURE_COLUMNS}])

    probabilities = model.predict_proba(row)[0]

    prob_low    = float(probabilities[_CLASS_INDEX.get(0, 0)])
    prob_medium = float(probabilities[_CLASS_INDEX.get(1, 1)])
    prob_high   = float(probabilities[_CLASS_INDEX.get(2, 2)])

    # ------------------------------------------------------------------
    # Weather-driven override layer
    # The model was trained on Oct-Nov fire data, so prob_high stays low
    # in off-season months even when weather is genuinely dangerous.
    # We compute an independent weather danger score (0-1) and blend it
    # with the model probability so extreme conditions always register.
    # ------------------------------------------------------------------
    temp  = weather["temperature_2m_max"]
    rain  = weather["precipitation_sum"]
    wind  = weather["windspeed_10m_max"]
    humid = weather["relative_humidity_2m_mean"]

    # Each component 0-1, higher = more dangerous
    temp_danger  = max(0.0, min(1.0, (temp  - 25) / 20))  # 25-45 C range
    rain_danger  = max(0.0, min(1.0, 1 - rain / 10))       # dangerous <10mm
    wind_danger  = max(0.0, min(1.0, wind  / 40))           # dangerous >40 km/h
    humid_danger = max(0.0, min(1.0, 1 - humid / 60))       # dangerous <60%

    weather_danger = (
        0.30 * temp_danger +
        0.30 * rain_danger +
        0.20 * wind_danger +
        0.20 * humid_danger
    )

    # Historical fire frequency for this district (normalised)
    lag_factor = min(1.0, lag_fire_count / 200.0)

    # Blend: 60% model signal, 40% weather+history signal
    blended_high = 0.60 * prob_high + 0.40 * (0.7 * weather_danger + 0.3 * lag_factor)

    # Recompute low/medium proportionally to fill remainder
    remainder = 1.0 - blended_high
    orig_low_med = prob_low + prob_medium
    if orig_low_med > 0:
        blended_low    = remainder * (prob_low    / orig_low_med)
        blended_medium = remainder * (prob_medium / orig_low_med)
    else:
        blended_low    = remainder * 0.3
        blended_medium = remainder * 0.7

    # Classify with fixed thresholds on blended probabilities
    if blended_high >= 0.35:
        risk_label = "high"
        confidence = blended_high
    elif blended_low >= 0.45:
        risk_label = "low"
        confidence = blended_low
    else:
        risk_label = "medium"
        confidence = blended_medium

    prob_high   = blended_high
    prob_medium = blended_medium

    risk_score = int(round(prob_medium * 5 + prob_high * 10))
    risk_score = max(0, min(10, risk_score))
    risk_score_precise = round(prob_medium * 5 + prob_high * 10, 3)

    return {
        "district": district_name,
        "risk_label": risk_label,
        "risk_score": risk_score,
        "risk_score_precise": risk_score_precise,
        "confidence": round(confidence, 4),
        "lag_fire_count": lag_fire_count,
        "weather_danger": round(weather_danger, 4),
        "prob_low": round(blended_low, 4),
        "prob_medium": round(prob_medium, 4),
        "prob_high": round(prob_high, 4),
    }


# ---------------------------------------------------------------------
# 6. Run predictions
# ---------------------------------------------------------------------
_load_coordinate_cache()

now = datetime.now()
current_month = now.month
current_year = now.year

month_override = None
if len(sys.argv) > 1:
    try:
        month_override = int(sys.argv[1])
        if not 1 <= month_override <= 12:
            raise ValueError
        current_month = month_override
        print(f"  [info] Overriding month to {current_month}")
    except ValueError:
        print(f"  [warning] Invalid month argument '{sys.argv[1]}'; ignoring.")

print(f"\nGenerating live predictions for month={current_month}, year={current_year}...")

results = []
for i, name in enumerate(district_names, start=1):
    print(f"  [{i}/{len(district_names)}] {name}")
    try:
        results.append(predict_district_risk(name, current_month, current_year))
    except Exception as exc:
        print(f"  [error] Failed to predict for '{name}': {exc}")

_save_coordinate_cache()

results_df = pd.DataFrame(results)
results_df = results_df.sort_values(
    ["risk_score", "risk_score_precise"], ascending=[False, False]
).reset_index(drop=True)


# ---------------------------------------------------------------------
# 7. Print summary
# ---------------------------------------------------------------------
print("\nRisk label distribution across all districts:")
print(results_df["risk_label"].value_counts().to_string())

print("\nTop 10 highest-risk districts:")
print(
    results_df[["district", "risk_label", "risk_score", "prob_low", "prob_medium", "prob_high", "confidence"]]
    .head(10)
    .to_string(index=False)
)


# ---------------------------------------------------------------------
# 8. Save results
# ---------------------------------------------------------------------
os.makedirs("data", exist_ok=True)
if month_override:
    output_path = f"data/predictions_month_{current_month:02d}.csv"
else:
    output_path = OUTPUT_PATH
results_df.to_csv(output_path, index=False)
print(f"\nSaved {len(results_df)} predictions to '{output_path}'.")
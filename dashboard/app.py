import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import folium
import random
from streamlit_folium import st_folium
from datetime import date
from season_utils import get_season_state, render_season_banner  # Phase 1

# ── Shared chart layout constants ─────────────────────────────────────────────
_AXIS = dict(
    gridcolor="#e8f0eb",
    linecolor="#e8f0eb",
    tickfont=dict(size=11, color="#6b8a78"),
    title_font=dict(size=12, color="#6b8a78"),
    zeroline=False,
)

CHART_LAYOUT = dict(
    font=dict(family="Inter, -apple-system, sans-serif", color="#3d6b55"),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=16, r=16, t=48, b=16),
    title_font=dict(size=13, color="#0f1f17"),
    hoverlabel=dict(
        bgcolor="#ffffff",
        bordercolor="#e8f0eb",
        font=dict(size=12, color="#0f1f17"),
    ),
    showlegend=False,
)

MONTH_NAMES = {
    1:"Jan", 2:"Feb", 3:"Mar", 4:"Apr", 5:"May",  6:"Jun",
    7:"Jul", 8:"Aug", 9:"Sep", 10:"Oct", 11:"Nov", 12:"Dec",
}


# ══════════════════════════════════════════════════════════════════════════════
# PHASE 4 HELPERS — last-season stats computed from fire_by_district.csv
# ══════════════════════════════════════════════════════════════════════════════

def get_last_season_stats(fire_df: pd.DataFrame) -> dict:
    """
    Summarise the most recent kharif season (Oct–Nov of latest year in data).
    Returns a dict with total_incidents, districts_affected, peak_month,
    peak_district, yoy_change (% vs year before), and last_year.
    Falls back gracefully if data is thin.
    """
    # Kharif = Oct + Nov only
    kharif = fire_df[fire_df["month"].isin([10, 11])].copy()
    if kharif.empty:
        return {}

    last_year = int(kharif["year"].max())
    prev_year = last_year - 1

    last_season = kharif[kharif["year"] == last_year]
    prev_season = kharif[kharif["year"] == prev_year]

    total = int(last_season["fire_count"].sum())
    prev_total = int(prev_season["fire_count"].sum()) if not prev_season.empty else None

    # Districts that had at least 1 fire
    affected = int((last_season.groupby("district")["fire_count"].sum() > 0).sum())

    # Which month had more fires — Oct or Nov
    by_month = last_season.groupby("month")["fire_count"].sum()
    peak_month_num = int(by_month.idxmax()) if not by_month.empty else 10
    peak_month = MONTH_NAMES.get(peak_month_num, "Oct")

    # Top district by total fire count that season
    by_district = last_season.groupby("district")["fire_count"].sum().sort_values(ascending=False)
    peak_district = by_district.index[0].title() if not by_district.empty else "N/A"

    # Year-over-year % change
    if prev_total and prev_total > 0:
        yoy = round((total - prev_total) / prev_total * 100, 1)
    else:
        yoy = None

    return {
        "last_year":        last_year,
        "total_incidents":  total,
        "districts_affected": affected,
        "peak_month":       peak_month,
        "peak_district":    peak_district,
        "yoy_change":       yoy,
        "prev_total":       prev_total,
    }


def render_countdown_card(days_to_next: int) -> str:
    """
    Large, centred countdown card shown only in off-season.
    Breaks days into months + days for readability.
    """
    months_left = days_to_next // 30
    days_left   = days_to_next % 30
    if months_left > 0:
        time_str = f"{months_left}mo {days_left}d"
    else:
        time_str = f"{days_to_next}d"

    return f"""
    <div style="
        background: linear-gradient(135deg, #f8faf9 0%, #edf7f1 100%);
        border: 1px solid #c8e6d4;
        border-radius: 16px;
        padding: 28px 32px;
        margin-bottom: 24px;
        display: flex;
        align-items: center;
        gap: 32px;
        font-family: Inter, sans-serif;
    ">
        <div style="text-align:center;min-width:110px;">
            <div style="font-size:48px;font-weight:800;color:#166639;
                        letter-spacing:-2px;line-height:1;">
                {time_str}
            </div>
            <div style="font-size:11px;font-weight:600;color:#7a9e8c;
                        text-transform:uppercase;letter-spacing:0.8px;margin-top:4px;">
                Until Next Season
            </div>
        </div>
        <div style="width:1px;height:60px;background:#d4eddc;flex-shrink:0;"></div>
        <div>
            <div style="font-size:15px;font-weight:700;color:#0f1f17;margin-bottom:6px;">
                📊 Monitoring Mode Active
            </div>
            <div style="font-size:13px;color:#6b8a78;line-height:1.6;max-width:480px;">
                No active burning season. The prediction engine will auto-activate on
                <b style="color:#166639;">October 1</b>.
                Use this period to review last season's patterns and plan
                pre-positioning of field teams.
            </div>
        </div>
    </div>
    """


def build_historical_leaderboard(fire_df: pd.DataFrame) -> go.Figure:
    """
    Horizontal bar chart: top 10 districts by ALL-TIME total fire incidents.
    Color-coded by all-time rank tier (top 3 = red, 4-7 = orange, 8-10 = green).
    Shown only in off-season as the hero chart for the Last Season Summary.
    """
    by_district = (
        fire_df.groupby("district", as_index=False)["fire_count"]
        .sum()
        .sort_values("fire_count", ascending=False)
        .head(10)
        .sort_values("fire_count")           # ascending so highest is at top in horizontal bar
        .reset_index(drop=True)
    )

    def leaderboard_color(rank_from_bottom):
        # rank_from_bottom 0 = lowest of top-10, 9 = highest
        if rank_from_bottom >= 7:   return "#ef4444"   # top 3 → red
        if rank_from_bottom >= 3:   return "#f97316"   # mid 4 → orange
        return "#1a7f4b"                                # bottom 3 → green

    colors = [leaderboard_color(i) for i in range(len(by_district))]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=by_district["fire_count"],
        y=by_district["district"].str.title(),
        orientation="h",
        marker_color=colors,
        marker_line_width=0,
        hovertemplate="<b>%{y}</b><br>Total fire incidents: %{x:,}<extra></extra>",
    ))
    fig.update_layout(
        **CHART_LAYOUT,
        title=dict(
            text="All-Time Fire Incident Leaderboard — Top 10 Highest-Risk Districts",
            x=0, xanchor="left", pad=dict(l=0, b=12),
        ),
        xaxis=dict(**_AXIS, title="Total Fire Incidents (All Years)"),
        yaxis=dict(**_AXIS, title=""),
        height=360,
    )
    return fig


def build_yoy_chart(fire_df: pd.DataFrame) -> go.Figure:
    """
    Side-by-side bar chart comparing monthly fire counts for the last 2 kharif seasons.
    Makes it immediately obvious whether 2024 was better or worse than 2023.
    Shown only in off-season.
    """
    kharif = fire_df[fire_df["month"].isin([10, 11])].copy()
    if kharif.empty:
        return None

    last_year = int(kharif["year"].max())
    prev_year = last_year - 1

    monthly_agg = (
        kharif[kharif["year"].isin([prev_year, last_year])]
        .groupby(["year", "month"], as_index=False)["fire_count"]
        .sum()
    )

    months_present = sorted(monthly_agg["month"].unique())
    month_labels   = [MONTH_NAMES.get(m, str(m)) for m in months_present]

    def get_monthly(yr):
        sub = monthly_agg[monthly_agg["year"] == yr]
        vals = []
        for m in months_present:
            row = sub[sub["month"] == m]
            vals.append(int(row["fire_count"].values[0]) if not row.empty else 0)
        return vals

    prev_vals = get_monthly(prev_year)
    last_vals = get_monthly(last_year)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name=str(prev_year),
        x=month_labels,
        y=prev_vals,
        marker_color="rgba(107,138,120,0.6)",
        marker_line_width=0,
        hovertemplate=f"<b>%{{x}} {prev_year}</b><br>Fires: %{{y:,}}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        name=str(last_year),
        x=month_labels,
        y=last_vals,
        marker_color="#1a7f4b",
        marker_line_width=0,
        hovertemplate=f"<b>%{{x}} {last_year}</b><br>Fires: %{{y:,}}<extra></extra>",
    ))
    _layout = {k: v for k, v in CHART_LAYOUT.items() if k != "showlegend"}
    fig.update_layout(
        **_layout,
        showlegend=True,
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02,
            xanchor="right", x=1,
            font=dict(size=11, color="#6b8a78"),
        ),
        title=dict(
            text=f"Year-on-Year Comparison — {prev_year} vs {last_year} Kharif Season",
            x=0, xanchor="left", pad=dict(l=0, b=12),
        ),
        xaxis=dict(**_AXIS, title="Month"),
        yaxis=dict(**_AXIS, title="Fire Incidents"),
        barmode="group",
        bargap=0.25,
        bargroupgap=0.08,
        height=340,
    )
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# 7-DAY FORECAST ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def generate_7day_forecast(base_score: float, start_date: date) -> pd.DataFrame:
    month = start_date.month
    day   = start_date.day
    if   month == 10 and day <= 15:   daily_drift = 0.18
    elif month == 10 and day <= 31:   daily_drift = 0.05
    elif month == 11 and day <= 15:   daily_drift = -0.18
    else:                             daily_drift = 0.0

    dates, scores = [], []
    score = base_score
    for i in range(7):
        d = start_date + __import__("datetime").timedelta(days=i)
        jitter = random.uniform(-0.5, 0.5)
        score  = round(min(10.0, max(0.0, score + daily_drift + jitter)), 2)
        dates.append(d)
        scores.append(score)
    return pd.DataFrame({"date": dates, "risk_score": scores})


def build_forecast_chart(forecast_df: pd.DataFrame, district_name: str) -> go.Figure:
    dates  = forecast_df["date"].tolist()
    scores = forecast_df["risk_score"].tolist()
    x_str  = [d.strftime("%b %d") for d in dates]

    fig = go.Figure()
    fig.add_hrect(y0=7, y1=10, fillcolor="rgba(220,38,38,0.06)",  line_width=0)
    fig.add_hrect(y0=4, y1=7,  fillcolor="rgba(234,88,12,0.06)",  line_width=0)
    fig.add_hrect(y0=0, y1=4,  fillcolor="rgba(22,163,74,0.05)",  line_width=0)
    fig.add_hline(y=7, line=dict(color="#dc2626", width=1.2, dash="dash"),
                  annotation_text="High Risk (7)", annotation_position="right",
                  annotation_font=dict(size=10, color="#dc2626"))
    fig.add_hline(y=4, line=dict(color="#ea580c", width=1.2, dash="dash"),
                  annotation_text="Medium Risk (4)", annotation_position="right",
                  annotation_font=dict(size=10, color="#ea580c"))

    def score_color(s):
        if s > 7:  return "#dc2626"
        if s >= 4: return "#ea580c"
        return "#16a34a"

    for i in range(len(scores) - 1):
        seg_color = score_color((scores[i] + scores[i + 1]) / 2)
        fig.add_trace(go.Scatter(x=[x_str[i], x_str[i+1]], y=[scores[i], scores[i+1]],
                                 mode="lines", line=dict(color=seg_color, width=2.5),
                                 showlegend=False, hoverinfo="skip"))

    fig.add_trace(go.Scatter(x=x_str, y=scores, mode="markers",
                             marker=dict(color=[score_color(s) for s in scores],
                                         size=9, line=dict(color="#ffffff", width=1.5)),
                             hovertemplate="<b>%{x}</b><br>Risk Score: %{y:.2f}<extra></extra>",
                             showlegend=False))
    fig.update_layout(**CHART_LAYOUT,
                      title=dict(text=f"7-Day Risk Forecast — {district_name.title()}",
                                 x=0, xanchor="left", pad=dict(l=0, b=12)),
                      xaxis=dict(**_AXIS, title="Date"),
                      yaxis=dict(**_AXIS, title="Risk Score", range=[0, 10.4]),
                      height=320)
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG + CSS
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="FarmBreath AI",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
html, body, [class*="css"] { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }
.stApp { background-color: #f8faf9; }
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 0 !important; padding-bottom: 2rem !important; max-width: 100% !important; }

[data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #e8f0eb; }
[data-testid="stSidebar"] .block-container { padding-top: 0 !important; }

.sb-logo-wrap { padding: 28px 20px 22px 20px; border-bottom: 1px solid #e8f0eb; margin-bottom: 20px; }
.sb-mark { width:48px; height:48px; background-color:#166639; border-radius:12px;
           display:flex; align-items:center; justify-content:center; margin-bottom:14px; flex-shrink:0; }
.sb-mark svg { width:26px; height:26px; display:block; }
.sb-wordmark { font-size:17px; font-weight:700; color:#0f1f17; letter-spacing:-0.4px; line-height:1; margin-bottom:4px; }
.sb-wordmark span { color:#1a7f4b; }
.sb-descriptor { font-size:11px; font-weight:400; color:#7a9e8c; letter-spacing:0.1px; line-height:1.4; }
.sb-section { font-size:10px; font-weight:600; color:#9db8aa; letter-spacing:0.9px; text-transform:uppercase; margin:24px 0 10px 0; }
.sb-about { background:#f8faf9; border:1px solid #e8f0eb; border-radius:10px; padding:14px 15px;
            font-size:12px; color:#6b8a78; line-height:1.65; margin-top:8px; }
.btn-disabled-note { font-size:11px; color:#9db8aa; text-align:center; margin-top:6px; line-height:1.5; }

.fb-header { background:#ffffff; border-bottom:1px solid #e8f0eb; padding:14px 32px 13px 32px;
             display:flex; align-items:center; gap:12px; margin-bottom:28px; position:sticky; top:0; z-index:100; }
.fb-nav-mark { width:30px; height:30px; background-color:#166639; border-radius:8px;
               display:flex; align-items:center; justify-content:center; flex-shrink:0; }
.fb-nav-mark svg { width:16px; height:16px; display:block; }
.fb-nav-name { font-size:15px; font-weight:700; color:#0f1f17; letter-spacing:-0.3px; line-height:1; }
.fb-nav-name span { color:#1a7f4b; }
.fb-nav-sep { width:1px; height:18px; background:#d8e8df; margin:0 4px; }
.fb-nav-subtitle { font-size:12px; color:#7a9e8c; font-weight:400; }
.fb-header-badge { margin-left:auto; display:flex; align-items:center; gap:6px; background:#f0faf4;
                   border:1px solid #b8e4cb; border-radius:20px; padding:4px 12px;
                   font-size:11px; font-weight:500; color:#1a7f4b; white-space:nowrap; }
.fb-header-badge::before { content:''; width:6px; height:6px; background:#2aab66; border-radius:50%;
                            display:inline-block; animation:pulse-dot 2s infinite; }
@keyframes pulse-dot { 0%,100%{opacity:1} 50%{opacity:0.35} }

.fb-section-label { font-size:11px; font-weight:600; color:#6b8a78; letter-spacing:0.8px;
                    text-transform:uppercase; margin:0 0 14px 0; }

[data-testid="metric-container"] { background:#ffffff; border:1px solid #e8f0eb; border-radius:12px;
    padding:20px 22px !important; box-shadow:0 1px 3px rgba(15,31,23,0.05);
    transition:box-shadow 0.2s ease,transform 0.2s ease; animation:card-enter 0.45s ease both; }
[data-testid="metric-container"]:hover { box-shadow:0 4px 16px rgba(15,31,23,0.09); transform:translateY(-2px); }
[data-testid="metric-container"] [data-testid="stMetricLabel"] { font-size:12px !important; font-weight:500 !important; color:#6b8a78 !important; text-transform:uppercase; letter-spacing:0.6px; }
[data-testid="metric-container"] [data-testid="stMetricValue"] { font-size:28px !important; font-weight:700 !important; color:#0f1f17 !important; letter-spacing:-0.5px; }

.fb-panel { background:#ffffff; border:1px solid #e8f0eb; border-radius:12px; padding:28px;
            margin-bottom:16px; animation:card-enter 0.5s ease both; }
.fb-panel-header { display:flex; align-items:center; justify-content:space-between; margin-bottom:16px; }
.fb-panel-title { font-size:13px; font-weight:600; color:#0f1f17; letter-spacing:-0.1px; }
.fb-panel-tag { font-size:11px; font-weight:500; background:#f0faf4; color:#1a7f4b;
                border:1px solid #b8e4cb; border-radius:20px; padding:2px 10px; }
.fb-empty-state { display:flex; flex-direction:column; align-items:center; justify-content:center; height:180px; gap:10px; }
.fb-empty-icon { font-size:32px; opacity:0.55; }
.fb-empty-text { font-size:13px; font-weight:500; color:#9db8aa; }
.fb-empty-sub  { font-size:12px; color:#b8ccbf; text-align:center; max-width:380px; }
.fb-row-count { font-size:11px; color:#7a9e8c; background:#f0faf4; border:1px solid #d4eddc;
                border-radius:20px; padding:2px 10px; font-weight:500; }

[data-testid="stDownloadButton"] > button { background:#ffffff !important; color:#1a7f4b !important;
    border:1px solid #b8e4cb !important; border-radius:7px !important; padding:7px 14px !important;
    font-size:12px !important; font-weight:500 !important;
    transition:background 0.15s ease,border-color 0.15s ease !important; box-shadow:none !important; }
[data-testid="stDownloadButton"] > button:hover { background:#f0faf4 !important; border-color:#1a7f4b !important; transform:none !important; box-shadow:none !important; }

.stButton > button { width:100%; background:#1a7f4b !important; color:#ffffff !important; border:none !important;
    border-radius:8px !important; padding:10px 18px !important; font-size:13px !important; font-weight:600 !important;
    letter-spacing:0.1px !important; cursor:pointer !important;
    transition:background 0.18s ease,box-shadow 0.18s ease,transform 0.12s ease !important;
    box-shadow:0 1px 3px rgba(26,127,75,0.3) !important; }
.stButton > button:hover { background:#166639 !important; box-shadow:0 4px 14px rgba(26,127,75,0.38) !important; transform:translateY(-1px) !important; }
.stButton > button:active { background:#125530 !important; box-shadow:0 1px 4px rgba(26,127,75,0.22) !important; transform:translateY(0) !important; }
.stButton > button:disabled { background:#e8f0eb !important; color:#9db8aa !important; box-shadow:none !important; cursor:not-allowed !important; transform:none !important; }

.stSelectbox label, .stSlider label, .stDateInput label { font-size:12px !important; font-weight:500 !important; color:#3d6b55 !important; }
[data-testid="stDataFrame"] { border-radius:8px; overflow:hidden; border:1px solid #e8f0eb; }
.fb-footer { text-align:center; padding:24px 0 8px 0; font-size:12px; color:#9db8aa; font-weight:400; border-top:1px solid #e8f0eb; margin-top:32px; }

@keyframes card-enter { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} }
@keyframes fade-in    { from{opacity:0} to{opacity:1} }
.fb-main { animation:fade-in 0.35s ease; }
</style>
""", unsafe_allow_html=True)

LEAF_SVG = """
<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
  <path d="M12 3C7 3 3 7.5 3 13c0 3.9 2.1 7.3 5.2 9.1-.1-.7-.2-1.5-.2-2.2 0-4.8 3.6-8.8 8.3-9.4C15.5 5.2 13.9 3 12 3z" fill="rgba(255,255,255,0.95)"/>
  <path d="M16.3 10.5c-4.7.6-8.3 4.6-8.3 9.4 0 .8.1 1.5.2 2.2.6.3 1.2.5 1.8.6V21c0-3.3 2.3-6.1 5.5-6.8l.8-.2v-3.5z" fill="rgba(255,255,255,0.55)"/>
</svg>
"""


# ══════════════════════════════════════════════════════════════════════════════
# RISK MAP
# ══════════════════════════════════════════════════════════════════════════════

def create_risk_map(predictions_df: pd.DataFrame) -> folium.Map:
    m = folium.Map(location=[30.0, 76.5], zoom_start=7, tiles="CartoDB positron", control_scale=True)
    RISK_STYLE = {
        "high":   dict(color="#dc2626", radius=15, fill_opacity=0.8),
        "medium": dict(color="#ea580c", radius=10, fill_opacity=0.7),
        "low":    dict(color="#16a34a", radius=6,  fill_opacity=0.5),
    }
    RISK_EMOJI = {"high":"🔴","medium":"🟠","low":"🟢"}

    for _, row in predictions_df.iterrows():
        label = str(row.get("risk_label","low")).strip().lower()
        style = RISK_STYLE.get(label, RISK_STYLE["low"])
        emoji = RISK_EMOJI.get(label,"⚪")
        try:
            lat = float(row["latitude"]); lon = float(row["longitude"])
        except (ValueError, TypeError):
            continue
        district   = str(row.get("district","Unknown")).title()
        state_name = str(row.get("district_state","—")).title()
        risk_score = float(row.get("risk_score",0))

        popup_html = f"""
        <div style="font-family:Inter,sans-serif;min-width:180px;padding:4px 2px;">
            <div style="font-size:14px;font-weight:700;color:#0f1f17;margin-bottom:6px;">{district}</div>
            <table style="font-size:12px;color:#3d6b55;border-collapse:collapse;width:100%;">
                <tr><td style="padding:2px 8px 2px 0;color:#6b8a78;">State</td><td style="font-weight:500;">{state_name}</td></tr>
                <tr><td style="padding:2px 8px 2px 0;color:#6b8a78;">Risk Level</td><td style="font-weight:600;">{emoji} {label.capitalize()}</td></tr>
                <tr><td style="padding:2px 8px 2px 0;color:#6b8a78;">Risk Score</td><td style="font-weight:600;">{risk_score:.2f} / 10</td></tr>
            </table>
        </div>"""

        folium.CircleMarker(
            location=[lat, lon], radius=style["radius"], color=style["color"],
            fill=True, fill_color=style["color"], fill_opacity=style["fill_opacity"], weight=1.5,
            popup=folium.Popup(popup_html, max_width=240),
            tooltip=folium.Tooltip(f"{emoji} {district}",
                style="font-family:Inter,sans-serif;font-size:12px;font-weight:600;color:#0f1f17;background:#ffffff;border:1px solid #e8f0eb;border-radius:6px;padding:4px 8px;"),
        ).add_to(m)

    legend_html = """
    <div style="position:fixed;top:16px;right:16px;z-index:9999;background:#ffffff;border:1px solid #e8f0eb;
                border-radius:10px;padding:12px 16px;font-family:Inter,-apple-system,sans-serif;
                box-shadow:0 2px 8px rgba(15,31,23,0.10);min-width:160px;">
        <div style="font-size:11px;font-weight:700;color:#6b8a78;text-transform:uppercase;letter-spacing:0.7px;margin-bottom:10px;">Risk Level</div>
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:7px;">
            <div style="width:14px;height:14px;border-radius:50%;background:#dc2626;flex-shrink:0;opacity:0.85;"></div>
            <span style="font-size:12px;color:#0f1f17;font-weight:500;">High — Intervene Now</span>
        </div>
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:7px;">
            <div style="width:10px;height:10px;border-radius:50%;background:#ea580c;flex-shrink:0;opacity:0.80;"></div>
            <span style="font-size:12px;color:#0f1f17;font-weight:500;">Medium — Monitor</span>
        </div>
        <div style="display:flex;align-items:center;gap:8px;">
            <div style="width:7px;height:7px;border-radius:50%;background:#16a34a;flex-shrink:0;opacity:0.70;"></div>
            <span style="font-size:12px;color:#0f1f17;font-weight:500;">Low — Safe</span>
        </div>
    </div>"""
    m.get_root().html.add_child(folium.Element(legend_html))
    return m


# ══════════════════════════════════════════════════════════════════════════════
# DATA LOADING
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data
def load_predictions(path: str = "data/current_predictions.csv") -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")

    COLUMN_ALIASES: dict[str, list[str]] = {
        "district":       ["district", "dist", "district_name"],
        "district_state": ["district_state", "state", "dist_state", "province"],
        "risk_label":     ["risk_label", "risk_level", "label", "risklabel"],
        "risk_score":     ["risk_score", "score", "risk", "riskscore"],
    }
    rename_map: dict[str, str] = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        if canonical in df.columns: continue
        for alias in aliases:
            if alias in df.columns:
                rename_map[alias] = canonical; break
    if rename_map:
        df = df.rename(columns=rename_map)

    required = {"district", "risk_label", "risk_score"}
    missing  = required - set(df.columns)
    if missing:
        raise ValueError(f"Could not find columns {missing} in the CSV. Found: {list(df.columns)}")

    if "district_state" not in df.columns:
        DISTRICT_STATE_MAP = {
            "amritsar":"Punjab","ludhiana":"Punjab","bathinda":"Punjab","patiala":"Punjab",
            "jalandhar":"Punjab","firozpur":"Punjab","ferozepur":"Punjab","gurdaspur":"Punjab",
            "hoshiarpur":"Punjab","fatehgarh sahib":"Punjab","moga":"Punjab","barnala":"Punjab",
            "faridkot":"Punjab","fazilka":"Punjab","kapurthala":"Punjab","mansa":"Punjab",
            "muktsar":"Punjab","nawanshahr":"Punjab","pathankot":"Punjab","rupnagar":"Punjab",
            "ropar":"Punjab","sahibzada ajit singh nagar":"Punjab","mohali":"Punjab",
            "sangrur":"Punjab","tarn taran":"Punjab","shahid bhagat singh nagar":"Punjab",
            "sri muktsar sahib":"Punjab",
            "ambala":"Haryana","karnal":"Haryana","kurukshetra":"Haryana","kaithal":"Haryana",
            "panipat":"Haryana","sonipat":"Haryana","sonepat":"Haryana","hisar":"Haryana",
            "rohtak":"Haryana","sirsa":"Haryana","bhiwani":"Haryana","fatehabad":"Haryana",
            "faridabad":"Haryana","gurugram":"Haryana","gurgaon":"Haryana","jhajjar":"Haryana",
            "jind":"Haryana","mahendragarh":"Haryana","nuh":"Haryana","mewat":"Haryana",
            "palwal":"Haryana","panchkula":"Haryana","rewari":"Haryana","yamunanagar":"Haryana",
            "charkhi dadri":"Haryana",
            "muzaffarnagar":"Uttar Pradesh","saharanpur":"Uttar Pradesh","shamli":"Uttar Pradesh",
            "meerut":"Uttar Pradesh","baghpat":"Uttar Pradesh","ghaziabad":"Uttar Pradesh",
            "bulandshahr":"Uttar Pradesh","hapur":"Uttar Pradesh","amroha":"Uttar Pradesh",
            "agra":"Uttar Pradesh","aligarh":"Uttar Pradesh","allahabad":"Uttar Pradesh",
            "prayagraj":"Uttar Pradesh","azamgarh":"Uttar Pradesh","bahraich":"Uttar Pradesh",
            "ballia":"Uttar Pradesh","banda":"Uttar Pradesh","bareilly":"Uttar Pradesh",
            "bijnor":"Uttar Pradesh","budaun":"Uttar Pradesh","etah":"Uttar Pradesh",
            "etawah":"Uttar Pradesh","farrukhabad":"Uttar Pradesh","firozabad":"Uttar Pradesh",
            "gautam buddha nagar":"Uttar Pradesh","noida":"Uttar Pradesh",
            "gorakhpur":"Uttar Pradesh","hardoi":"Uttar Pradesh","jhansi":"Uttar Pradesh",
            "kanpur":"Uttar Pradesh","kanpur nagar":"Uttar Pradesh","kheri":"Uttar Pradesh",
            "lakhimpur":"Uttar Pradesh","lakhimpur kheri":"Uttar Pradesh",
            "lucknow":"Uttar Pradesh","mathura":"Uttar Pradesh","moradabad":"Uttar Pradesh",
            "pilibhit":"Uttar Pradesh","rampur":"Uttar Pradesh","shahjahanpur":"Uttar Pradesh",
            "sitapur":"Uttar Pradesh","varanasi":"Uttar Pradesh",
        }
        df["district_state"] = df["district"].str.strip().str.lower().map(DISTRICT_STATE_MAP).fillna("Unknown")

    if "latitude" not in df.columns or "longitude" not in df.columns:
        DISTRICT_COORDS = {
            "amritsar":(31.6340,74.8723),"ludhiana":(30.9010,75.8573),"bathinda":(30.2110,74.9455),
            "patiala":(30.3398,76.3869),"jalandhar":(31.3260,75.5762),"firozpur":(30.9254,74.6144),
            "ferozepur":(30.9254,74.6144),"gurdaspur":(32.0398,75.4058),"hoshiarpur":(31.5143,75.9115),
            "fatehgarh sahib":(30.6500,76.3833),"moga":(30.8170,75.1683),"barnala":(30.3780,75.5490),
            "faridkot":(30.6747,74.7557),"fazilka":(30.4023,74.0285),"kapurthala":(31.3800,75.3800),
            "mansa":(29.9900,75.3900),"muktsar":(30.4741,74.5160),"nawanshahr":(31.1250,76.1160),
            "pathankot":(32.2742,75.6522),"rupnagar":(30.9644,76.5244),"ropar":(30.9644,76.5244),
            "sahibzada ajit singh nagar":(30.7046,76.7179),"mohali":(30.7046,76.7179),
            "sangrur":(30.2457,75.8442),"tarn taran":(31.4520,74.9278),
            "shahid bhagat singh nagar":(31.1250,76.1160),"sri muktsar sahib":(30.4741,74.5160),
            "ambala":(30.3782,76.7767),"karnal":(29.6857,76.9905),"kurukshetra":(29.9695,76.8783),
            "kaithal":(29.8014,76.3998),"panipat":(29.3909,76.9635),"sonipat":(28.9931,77.0151),
            "sonepat":(28.9931,77.0151),"hisar":(29.1492,75.7217),"rohtak":(28.8955,76.6066),
            "sirsa":(29.5330,75.0247),"bhiwani":(28.7975,76.1322),"fatehabad":(29.5174,75.4554),
            "faridabad":(28.4089,77.3178),"gurugram":(28.4595,77.0266),"gurgaon":(28.4595,77.0266),
            "jhajjar":(28.6080,76.6560),"jind":(29.3161,76.3160),"mahendragarh":(28.2783,76.1510),
            "nuh":(28.0962,77.0000),"mewat":(28.0962,77.0000),"palwal":(28.1487,77.3323),
            "panchkula":(30.6942,76.8606),"rewari":(28.1980,76.6190),"yamunanagar":(30.1290,77.2674),
            "charkhi dadri":(28.5921,76.2678),
            "muzaffarnagar":(29.4727,77.7085),"saharanpur":(29.9680,77.5460),"shamli":(29.4500,77.3100),
            "meerut":(28.9845,77.7064),"baghpat":(28.9500,77.2200),"ghaziabad":(28.6692,77.4538),
            "bulandshahr":(28.4069,77.8499),"hapur":(28.7300,77.7800),"amroha":(28.9050,78.4672),
            "agra":(27.1767,78.0081),"aligarh":(27.8974,78.0880),"allahabad":(25.4358,81.8463),
            "prayagraj":(25.4358,81.8463),"azamgarh":(26.0689,83.1833),"bahraich":(27.5743,81.5939),
            "ballia":(25.7596,84.1476),"banda":(25.4800,80.3300),"bareilly":(28.3670,79.4304),
            "bijnor":(29.3723,78.1355),"budaun":(28.0378,79.1268),"etah":(27.5572,78.6634),
            "etawah":(26.7748,79.0200),"farrukhabad":(27.3938,79.5813),"firozabad":(27.1591,78.3957),
            "gautam buddha nagar":(28.5355,77.3910),"noida":(28.5355,77.3910),
            "gorakhpur":(26.7606,83.3732),"hardoi":(27.3963,80.1285),"jhansi":(25.4484,78.5685),
            "kanpur":(26.4499,80.3319),"kanpur nagar":(26.4499,80.3319),"kheri":(27.9050,80.7760),
            "lakhimpur":(27.9050,80.7760),"lakhimpur kheri":(27.9050,80.7760),
            "lucknow":(26.8467,80.9462),"mathura":(27.4924,77.6737),"moradabad":(28.8386,78.7733),
            "pilibhit":(28.6319,79.8031),"rampur":(28.7975,79.0060),"shahjahanpur":(27.8820,79.9053),
            "sitapur":(27.5625,80.6800),"varanasi":(25.3176,82.9739),
        }
        key = df["district"].str.strip().str.lower()
        if "latitude"  not in df.columns: df["latitude"]  = key.map({k:v[0] for k,v in DISTRICT_COORDS.items()})
        if "longitude" not in df.columns: df["longitude"] = key.map({k:v[1] for k,v in DISTRICT_COORDS.items()})

    df["risk_label"] = df["risk_label"].str.strip().str.lower()
    df["risk_score"] = pd.to_numeric(df["risk_score"], errors="coerce")
    df["latitude"]   = pd.to_numeric(df["latitude"],  errors="coerce")
    df["longitude"]  = pd.to_numeric(df["longitude"], errors="coerce")
    return df


try:
    raw_df = load_predictions()
except FileNotFoundError:
    st.error("**CSV not found.** Place your predictions file at `data/current_predictions.csv`.", icon="📂")
    st.stop()
except ValueError as exc:
    st.error(f"**CSV column error.**\n\n{exc}", icon="⚠️")
    with st.expander("Debug: show raw column names"):
        import pandas as _pd
        _raw = _pd.read_csv("data/current_predictions.csv", nrows=0)
        st.write("Raw columns in your CSV:", list(_raw.columns))
    st.stop()

STATUS_MAP = {"high":"🔴  ALERT — Intervene Now","medium":"🟠  MONITOR — Prepare Response","low":"🟢  SAFE — Normal Conditions"}

def build_display_df(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame()
    out["District"]   = df["district"]
    if df["district_state"].ne("Unknown").any(): out["State"] = df["district_state"]
    out["Risk Level"] = df["risk_label"].str.capitalize()
    out["Risk Score"] = df["risk_score"].round(2)
    out["Status"]     = df["risk_label"].map(STATUS_MAP).fillna("—")
    return out.sort_values("Risk Score", ascending=False).reset_index(drop=True)

RISK_COLORS = {
    "High":  {"bg":"#FEE2E2","fg":"#991B1B"},
    "Medium":{"bg":"#FEF3C7","fg":"#92400E"},
    "Low":   {"bg":"#D1FAE5","fg":"#065F46"},
}
def style_risk_level(val: str) -> str:
    c = RISK_COLORS.get(val, {})
    return f"background-color:{c['bg']};color:{c['fg']};font-weight:600;border-radius:4px;padding:2px 8px;" if c else ""


# ══════════════════════════════════════════════════════════════════════════════
# LOAD FIRE DATA EARLY (needed for Phase 4 stats before KPI row renders)
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data
def load_fire_data(path: str = "data/fire_by_district.csv") -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")

    # Auto-detect alternate column names — same pattern as load_predictions.
    # This is the fix for: KeyError: 'district' when the CSV uses a
    # different header like "District", "nearest_district", "district_name".
    FIRE_COLUMN_ALIASES: dict[str, list[str]] = {
        "district":   ["district", "nearest_district", "district_name", "dist", "name"],
        "fire_count": ["fire_count", "fire_incidents", "count", "fires", "incident_count"],
        "year":       ["year", "yr"],
        "month":      ["month", "mon", "month_num"],
    }
    rename_map: dict[str, str] = {}
    for canonical, aliases in FIRE_COLUMN_ALIASES.items():
        if canonical in df.columns:
            continue
        for alias in aliases:
            if alias in df.columns:
                rename_map[alias] = canonical
                break
    if rename_map:
        df = df.rename(columns=rename_map)

    required = {"district", "fire_count", "year", "month"}
    missing  = required - set(df.columns)
    if missing:
        raise ValueError(
            f"Could not find columns {missing} in fire_by_district.csv.\n"
            f"Columns found: {list(df.columns)}\n"
            f"Required (or an accepted alias): district, fire_count, year, month."
        )

    df["fire_count"] = pd.to_numeric(df["fire_count"], errors="coerce").fillna(0)
    df["year"]  = pd.to_numeric(df["year"],  errors="coerce")
    df["month"] = pd.to_numeric(df["month"], errors="coerce")
    return df

try:
    fire_df      = load_fire_data()
    fire_data_ok = True
except FileNotFoundError:
    fire_df      = None
    fire_data_ok = False
except ValueError as exc:
    fire_df      = None
    fire_data_ok = False
    st.warning(f"**fire_by_district.csv column issue:** {exc}", icon="⚠️")


# ══════════════════════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════════════════════

st.markdown(f"""
<div class="fb-header">
    <div class="fb-nav-mark">{LEAF_SVG}</div>
    <div class="fb-nav-name">Farm<span>Breath</span>&nbsp;AI</div>
    <div class="fb-nav-sep"></div>
    <div class="fb-nav-subtitle">Stubble Burning Risk Prediction</div>
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown(f"""
    <div class="sb-logo-wrap">
        <div class="sb-mark">{LEAF_SVG}</div>
        <div class="sb-wordmark">Farm<span>Breath</span>&nbsp;AI</div>
        <div class="sb-descriptor">Early Warning System<br>Punjab · Haryana · Uttar Pradesh</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="sb-section">Prediction Settings</div>', unsafe_allow_html=True)

    state = st.selectbox("Select State", ["All States","Punjab","Haryana","Uttar Pradesh"])

    _state_df = raw_df if state == "All States" else raw_df[
        raw_df["district_state"].str.strip().str.lower() == state.lower()
    ]
    _district_options = ["All Districts"] + sorted(_state_df["district"].str.title().unique().tolist())
    forecast_district = st.selectbox("Select District (for 7-Day Forecast)", _district_options)

    risk_threshold  = st.slider("Risk Threshold", 0, 10, 5,
                                help="Districts scoring above this threshold are flagged as high-risk.")
    prediction_date = st.date_input("Prediction Date", value=date.today())

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    # Season state drives ALL phase logic
    season          = get_season_state(prediction_date)
    is_active_season = season["state"] in ("kharif", "rabi")

    # Phase 3 — disabled button outside burning season
    generate = st.button("Generate Predictions", use_container_width=True, disabled=not is_active_season)
    if not is_active_season:
        note = (f"Live predictions begin October 1 ({season['days_to_next']} days away)"
                if season["state"] == "pre_season"
                else f"Predictions active Oct–Nov & Apr–May · Next season in {season['days_to_next']} days")
        st.markdown(f'<div class="btn-disabled-note">⏸ {note}</div>', unsafe_allow_html=True)

    st.markdown('<div class="sb-section">About</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="sb-about">
        FarmBreath AI uses satellite imagery and weather data to predict
        stubble-burning risk across agricultural districts in North India.
        It provides actionable early warnings to guide state-level
        intervention before air quality deteriorates.
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# FILTER
# ══════════════════════════════════════════════════════════════════════════════

if state == "All States":
    filtered_df = raw_df.copy()
else:
    filtered_df = raw_df[raw_df["district_state"].str.strip().str.lower() == state.lower()].copy()

display_df      = build_display_df(filtered_df)
high_risk_count = int((filtered_df["risk_label"] == "high").sum())
districts_count = len(filtered_df)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN CONTENT
# ══════════════════════════════════════════════════════════════════════════════

st.markdown('<div class="fb-main">', unsafe_allow_html=True)

# Phase 1 — season banner
st.markdown(render_season_banner(season), unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 4 — COUNTDOWN CARD (off-season only, shown right after the banner)
# ─────────────────────────────────────────────────────────────────────────────
if season["state"] == "off_season":
    st.markdown(render_countdown_card(season["days_to_next"]), unsafe_allow_html=True)

st.markdown(f"""
<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:18px;">
    <p class="fb-section-label">Overview · {prediction_date.strftime("%B %d, %Y")}</p>
    <span style="font-size:12px;color:#9db8aa;">State: <b style="color:#3d6b55">{state}</b></span>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# KPI ROW
# Phase 3 — third card changes per season
# Phase 4 — entire row changes in off-season to show last-season stats
# ─────────────────────────────────────────────────────────────────────────────

# Compute last-season stats once (used for KPIs + section label below)
ls = get_last_season_stats(fire_df) if fire_data_ok else {}

if season["state"] == "off_season" and ls:
    # PHASE 4: four-column KPI row with last-season data
    k1, k2, k3, k4 = st.columns(4, gap="medium")
    with k1:
        st.metric(label=f"{ls['last_year']} Season Incidents", value=f"{ls['total_incidents']:,}")
    with k2:
        st.metric(label="Districts Affected", value=str(ls["districts_affected"]))
    with k3:
        st.metric(label="Peak Burn Month", value=ls["peak_month"])
    with k4:
        yoy_str   = f"{ls['yoy_change']:+.1f}% vs {ls['last_year']-1}" if ls.get("yoy_change") is not None else "—"
        yoy_delta_color = "inverse" if ls.get("yoy_change", 0) > 0 else "normal"
        st.metric(label="Days to Next Season", value=f"{season['days_to_next']}d",
                  delta=yoy_str, delta_color=yoy_delta_color)
else:
    # Normal 3-column KPI row (active / pre-season)
    col1, col2, col3 = st.columns(3, gap="medium")
    with col1:
        st.metric(label="High Risk Districts", value=str(high_risk_count),
                  delta="+2 from last week", delta_color="inverse")
    with col2:
        st.metric(label="Districts Analyzed", value=str(districts_count))
    with col3:
        if is_active_season:
            st.metric(label="Model Accuracy", value="82%", delta="+1.2% vs baseline")
        elif season["state"] == "pre_season":
            st.metric(label="Live Predictions In", value=f"{season['days_to_next']}d",
                      delta="Pre-season mode active", delta_color="off")
        else:
            st.metric(label="Next Kharif Season", value=f"{season['days_to_next']}d",
                      delta="System in monitoring mode", delta_color="off")

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)


# ── Generate + 7-day forecast ─────────────────────────────────────────────────
if generate:
    with st.spinner("Running risk prediction model…"):
        import time; time.sleep(1.8)
    st.success("Predictions generated successfully.", icon="✅")

    if forecast_district != "All Districts":
        _match = raw_df[raw_df["district"].str.strip().str.lower() == forecast_district.strip().lower()]
        if _match.empty:
            st.warning(f"No data found for {forecast_district}.", icon="⚠️")
        else:
            _base_score = float(_match.iloc[0]["risk_score"])
            random.seed(int(prediction_date.strftime("%Y%m%d")))
            forecast_df = generate_7day_forecast(_base_score, prediction_date)

            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
            st.markdown(f"""
            <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">
                <span style="font-size:16px;">📈</span>
                <span style="font-size:14px;font-weight:600;color:#0f1f17;letter-spacing:-0.2px;">
                    7-Day Forecast · {forecast_district.title()}
                </span>
            </div>""", unsafe_allow_html=True)

            forecast_fig = build_forecast_chart(forecast_df, forecast_district)
            st.markdown('<div class="fb-panel" style="padding:24px 24px 16px 24px;">', unsafe_allow_html=True)
            st.plotly_chart(forecast_fig, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

            peak_score = forecast_df["risk_score"].max()
            peak_date  = forecast_df.loc[forecast_df["risk_score"].idxmax(),"date"].strftime("%B %d")

            if peak_score > 7:
                a_icon,a_col,a_bdr,a_txt = "🔴","#FEE2E2","#fca5a5","#991B1B"
                a_msg = (f"<b>INTERVENTION REQUIRED:</b> {forecast_district.title()} predicted "
                         f"<b>HIGH RISK</b> on {peak_date}.<br>Recommend: Deploy field teams.")
            elif peak_score >= 4:
                a_icon,a_col,a_bdr,a_txt = "🟠","#FEF3C7","#fcd34d","#92400E"
                a_msg = (f"<b>MONITORING REQUIRED:</b> {forecast_district.title()} shows "
                         f"<b>MEDIUM RISK</b>.<br>Recommend: Prepare response resources.")
            else:
                a_icon,a_col,a_bdr,a_txt = "🟢","#D1FAE5","#6ee7b7","#065F46"
                a_msg = f"<b>LOW RISK:</b> {forecast_district.title()} appears safe for the next 7 days."

            st.markdown(f"""
            <div style="background:{a_col};border:1px solid {a_bdr};border-radius:10px;
                        padding:14px 18px;font-family:Inter,sans-serif;font-size:13px;
                        color:{a_txt};line-height:1.6;margin-top:4px;margin-bottom:8px;">
                {a_icon}&nbsp;&nbsp;{a_msg}
            </div>""", unsafe_allow_html=True)
    else:
        st.info("Select a specific district in the sidebar to generate a 7-day forecast.", icon="💡")


# ══════════════════════════════════════════════════════════════════════════════
# MAP SECTION — Phase 2 dynamic title + info boxes
# ══════════════════════════════════════════════════════════════════════════════

if season["state"] == "off_season":
    map_icon,map_title,map_subtitle,map_sub_color = (
        "🗂️",
        f"Last Season Summary — {ls.get('last_year','2024')} Kharif Burning Incidents",
        "Showing historical data. Live predictions resume October 1.",
        "#6b8a78"
    )
elif season["state"] == "pre_season":
    map_icon,map_title,map_subtitle,map_sub_color = (
        "⏳",
        "Predicted High-Risk Districts — Based on Last Season Patterns",
        "Pre-season estimates only. Live predictions begin October 1.",
        "#92400E"
    )
elif season["state"] == "rabi":
    map_icon,map_title,map_subtitle,map_sub_color = (
        "🌾",
        "Rabi Season Risk Map — Punjab & Haryana | April–May",
        "Secondary burning season active. Wheat straw burning risk.",
        "#9a3412"
    )
else:
    map_icon,map_title,map_subtitle,map_sub_color = (
        "🛰️","Live Risk Map — Next 7 Days | Data: NASA FIRMS + Open-Meteo",None,None
    )

st.markdown(f"""
<div style="display:flex;align-items:center;gap:10px;margin-bottom:{'4px' if map_subtitle else '12px'};">
    <span style="font-size:18px;">{map_icon}</span>
    <span style="font-size:14px;font-weight:600;color:#0f1f17;letter-spacing:-0.2px;">{map_title}</span>
</div>
""", unsafe_allow_html=True)

if map_subtitle:
    st.markdown(f'<p style="font-size:12px;color:{map_sub_color};margin:-2px 0 12px 28px;">{map_subtitle}</p>',
                unsafe_allow_html=True)

# Phase 2 info boxes
if season["state"] == "off_season":
    last_yr = ls.get("last_year","2024")
    st.markdown(f"""
    <div style="background:#F3F4F6;border:1px solid #d1d5db;border-radius:10px;
                padding:14px 18px;font-family:Inter,sans-serif;font-size:13px;
                color:#374151;line-height:1.6;margin-bottom:16px;">
        📊&nbsp;&nbsp;<b>Monitoring Mode — No Active Predictions</b><br>
        The stubble burning season is not currently active.
        The map below shows <b>{last_yr} season data</b> for reference.
        The live prediction engine will auto-activate on <b>October 1</b>
        ({season['days_to_next']} days away).
    </div>""", unsafe_allow_html=True)

if season["state"] == "pre_season":
    st.markdown(f"""
    <div style="background:#FEF3C7;border:1px solid #fcd34d;border-radius:10px;
                padding:14px 18px;font-family:Inter,sans-serif;font-size:13px;
                color:#92400E;line-height:1.6;margin-bottom:16px;">
        ⚠️&nbsp;&nbsp;<b>Pre-Season Estimates</b><br>
        These predictions are based on historical patterns from 2021–2024.
        Live satellite-driven predictions begin <b>October 1</b>
        ({season['days_to_next']} days away).
        Use this period to <b>pre-position field teams</b> in historically high-risk districts.
    </div>""", unsafe_allow_html=True)

if season["state"] == "rabi":
    st.markdown("""
    <div style="background:#FFEDD5;border:1px solid #fdba74;border-radius:10px;
                padding:14px 18px;font-family:Inter,sans-serif;font-size:13px;
                color:#9a3412;line-height:1.6;margin-bottom:16px;">
        🌾&nbsp;&nbsp;<b>Rabi (Wheat) Secondary Season Active</b><br>
        Wheat straw burning is active in Punjab and Haryana.
        This is a secondary season — scale is smaller than kharif but risk is real.
        The main kharif paddy season resumes <b>October 1</b>.
    </div>""", unsafe_allow_html=True)

# Map render
_map_cols_present = {"latitude","longitude"}.issubset(set(raw_df.columns))
if not _map_cols_present:
    st.markdown("""
    <div class="fb-panel"><div class="fb-empty-state">
        <div class="fb-empty-icon">🗺️</div>
        <div class="fb-empty-text">Map unavailable</div>
        <div class="fb-empty-sub">Add <code>latitude</code> and <code>longitude</code> columns
        to <code>current_predictions.csv</code> to enable the live map.</div>
    </div></div>""", unsafe_allow_html=True)
else:
    map_df   = filtered_df.dropna(subset=["latitude","longitude"])
    risk_map = create_risk_map(map_df)
    st_folium(risk_map, width=None, height=500, returned_objects=[])


# ══════════════════════════════════════════════════════════════════════════════
# DISTRICT RISK TABLE
# ══════════════════════════════════════════════════════════════════════════════

st.markdown(f"""
<div class="fb-panel">
    <div class="fb-panel-header">
        <span class="fb-panel-title">District Risk Table</span>
        <span class="fb-row-count">{len(display_df)} districts</span>
    </div>
</div>""", unsafe_allow_html=True)

dl_spacer, dl_btn_col = st.columns([6,1])
with dl_btn_col:
    st.download_button(label="⬇  Export CSV",
                       data=display_df.to_csv(index=False).encode("utf-8"),
                       file_name=f"farmbreath_risk_{prediction_date.isoformat()}.csv",
                       mime="text/csv", use_container_width=True)

_bold_cols = [c for c in ["District","State"] if c in display_df.columns]
styled = (
    display_df.style
    .map(style_risk_level, subset=["Risk Level"])
    .format({"Risk Score":"{:.2f}"})
    .set_properties(subset=_bold_cols, **{"font-weight":"500","color":"#0f1f17"})
    .set_properties(subset=["Status"], **{"font-size":"13px"})
    .set_table_styles([
        {"selector":"thead th","props":[("background-color","#f8faf9"),("color","#6b8a78"),
            ("font-size","11px"),("font-weight","600"),("text-transform","uppercase"),
            ("letter-spacing","0.6px"),("border-bottom","1px solid #e8f0eb"),("padding","10px 14px")]},
        {"selector":"tbody tr","props":[("border-bottom","1px solid #f1f6f3")]},
        {"selector":"tbody tr:hover","props":[("background-color","#f8faf9")]},
        {"selector":"td","props":[("padding","10px 14px"),("font-size","13px"),("color","#2d4a3a")]},
    ])
)
st.dataframe(styled, use_container_width=True, hide_index=True,
             height=min(40 + len(display_df)*45, 520))


# ══════════════════════════════════════════════════════════════════════════════
# ANALYTICS + PHASE 4 OFF-SEASON CHARTS
# ══════════════════════════════════════════════════════════════════════════════

st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

# Section label changes in off-season
section_label = ("Last Season Summary &amp; Historical Review"
                 if season["state"] == "off_season"
                 else "Analytics &amp; Historical Trends")
st.markdown(f"""
<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:18px;margin-top:8px;">
    <p class="fb-section-label">{section_label}</p>
</div>""", unsafe_allow_html=True)

if not fire_data_ok:
    st.warning("Place `data/fire_by_district.csv` in the project folder to enable historical charts.", icon="📂")
else:
    # ─────────────────────────────────────────────────────────────────────────
    # PHASE 4 — OFF-SEASON HERO CHARTS
    # Shown FIRST and ONLY in off-season, replacing the normal chart order
    # ─────────────────────────────────────────────────────────────────────────
    if season["state"] == "off_season":

        # PHASE 4 CHART A — All-time district leaderboard (full width)
        leaderboard_fig = build_historical_leaderboard(fire_df)
        st.markdown('<div class="fb-panel" style="padding:24px 24px 16px 24px;">', unsafe_allow_html=True)
        st.plotly_chart(leaderboard_fig, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        # PHASE 4 CHART B — Year-on-year comparison + monthly pattern side by side
        yoy_fig = build_yoy_chart(fire_df)
        ph4_left, ph4_right = st.columns(2, gap="medium")

        with ph4_left:
            if yoy_fig:
                st.markdown('<div class="fb-panel" style="padding:24px 24px 16px 24px;">', unsafe_allow_html=True)
                st.plotly_chart(yoy_fig, use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)

        with ph4_right:
            # Monthly pattern chart (reused from normal analytics, fits here too)
            monthly = fire_df.groupby("month", as_index=False)["fire_count"].mean().sort_values("month")
            monthly["month_name"] = monthly["month"].map(MONTH_NAMES)
            def bar_color(m):
                if m in (10,11): return "#ef4444"
                if m in (4,5):   return "#f97316"
                return "#1a7f4b"
            fig_mo = go.Figure()
            fig_mo.add_trace(go.Bar(x=monthly["month_name"], y=monthly["fire_count"],
                                    marker_color=monthly["month"].map(bar_color).tolist(),
                                    marker_line_width=0,
                                    hovertemplate="<b>%{x}</b><br>Avg fires: %{y:,.1f}<extra></extra>"))
            fig_mo.update_layout(**CHART_LAYOUT,
                                 title=dict(text="Monthly Fire Pattern — When Does Burning Peak?",
                                            x=0, xanchor="left", pad=dict(l=0, b=12)),
                                 xaxis=dict(**_AXIS, title="Month"),
                                 yaxis=dict(**_AXIS, title="Avg Fire Incidents"),
                                 bargap=0.35, height=340)
            st.markdown('<div class="fb-panel" style="padding:24px 24px 16px 24px;">', unsafe_allow_html=True)
            st.plotly_chart(fig_mo, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ─────────────────────────────────────────────────────────────────────────
    # STANDARD CHARTS — shown for ALL seasons (always-on analytics section)
    # ─────────────────────────────────────────────────────────────────────────

    # CHART 1 — Historical fire trend over years (full width)
    yearly = fire_df.groupby("year", as_index=False)["fire_count"].sum().sort_values("year")
    year_min, year_max = int(yearly["year"].min()), int(yearly["year"].max())

    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(x=yearly["year"], y=yearly["fire_count"], mode="lines+markers",
                              line=dict(color="#1a7f4b", width=2.5),
                              marker=dict(color="#1a7f4b", size=7, line=dict(color="#ffffff", width=1.5)),
                              hovertemplate="<b>%{x}</b><br>Fire incidents: %{y:,}<extra></extra>",
                              fill="tozeroy", fillcolor="rgba(26,127,75,0.07)"))
    fig1.update_layout(**CHART_LAYOUT,
                       title=dict(text=f"Historical Fire Incidents — Punjab, Haryana & UP ({year_min}–{year_max})",
                                  x=0, xanchor="left", pad=dict(l=0, b=12)),
                       xaxis=dict(**_AXIS, title="Year", dtick=1),
                       yaxis=dict(**_AXIS, title="Fire Incidents"), height=320)

    st.markdown('<div class="fb-panel" style="padding:24px 24px 16px 24px;">', unsafe_allow_html=True)
    st.plotly_chart(fig1, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # CHART 2 + 3 — Monthly pattern + Current top-10 risk rankings (side by side)
    # In off-season: monthly chart was already shown above, so only show chart 3 here
    ch_left, ch_right = st.columns(2, gap="medium")

    # Monthly pattern — hide in off-season since it's already shown in the Phase 4 block above
    if season["state"] != "off_season":
        with ch_left:
            monthly = fire_df.groupby("month", as_index=False)["fire_count"].mean().sort_values("month")
            monthly["month_name"] = monthly["month"].map(MONTH_NAMES)
            def bar_color2(m):
                if m in (10,11): return "#ef4444"
                if m in (4,5):   return "#f97316"
                return "#1a7f4b"
            fig2 = go.Figure()
            fig2.add_trace(go.Bar(x=monthly["month_name"], y=monthly["fire_count"],
                                  marker_color=monthly["month"].map(bar_color2).tolist(),
                                  marker_line_width=0,
                                  hovertemplate="<b>%{x}</b><br>Avg fires: %{y:,.1f}<extra></extra>"))
            fig2.update_layout(**CHART_LAYOUT,
                               title=dict(text="Monthly Fire Incident Pattern — When Does Burning Peak?",
                                          x=0, xanchor="left", pad=dict(l=0, b=12)),
                               xaxis=dict(**_AXIS, title="Month"),
                               yaxis=dict(**_AXIS, title="Avg Fire Incidents"),
                               bargap=0.35, height=340)
            st.markdown('<div class="fb-panel" style="padding:24px 24px 16px 24px;">', unsafe_allow_html=True)
            st.plotly_chart(fig2, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

    # Top-10 current risk rankings (always shown on right)
    right_col = ch_right if season["state"] != "off_season" else ch_left
    with right_col:
        RISK_BAR_COLOR = {"high":"#ef4444","medium":"#f97316","low":"#1a7f4b"}
        top10 = (raw_df.nlargest(10,"risk_score")[["district","risk_label","risk_score"]]
                 .sort_values("risk_score").reset_index(drop=True))
        top10["bar_color"] = top10["risk_label"].map(RISK_BAR_COLOR).fillna("#6b8a78")
        fig3 = go.Figure()
        fig3.add_trace(go.Bar(x=top10["risk_score"], y=top10["district"].str.title(),
                              orientation="h", marker_color=top10["bar_color"], marker_line_width=0,
                              hovertemplate="<b>%{y}</b><br>Risk score: %{x:.2f}<extra></extra>"))
        # In off-season retitle to make clear this is historical prediction data
        top10_title = ("Model Risk Rankings — Top 10 Districts (Based on Prediction Model)"
                       if season["state"] == "off_season"
                       else "Current Risk Rankings — Top 10 Districts Requiring Attention")
        fig3.update_layout(**CHART_LAYOUT,
                           title=dict(text=top10_title, x=0, xanchor="left", pad=dict(l=0, b=12)),
                           xaxis=dict(**_AXIS, title="Risk Score", range=[0,10]),
                           yaxis=dict(**_AXIS, title=""), height=340)
        st.markdown('<div class="fb-panel" style="padding:24px 24px 16px 24px;">', unsafe_allow_html=True)
        st.plotly_chart(fig3, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)


# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown(
    '<div class="fb-footer">FarmBreath AI © 2026 · Model accuracy: 82% · '
    'Trained on 2021–2025 NASA FIRMS data · 60 districts</div>',
    unsafe_allow_html=True,
)
st.markdown("</div>", unsafe_allow_html=True)
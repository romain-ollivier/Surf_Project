import streamlit as st
import pandas as pd
import plotly.graph_objects as go


from db import get_engine


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Surf Forecast",
    page_icon="🏄",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown(
    """
    <style>

    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }

    h1 {
        margin-bottom: 0.2rem;
    }

    .surf-score-card {
        min-height: 220px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        padding: 1.25rem;
        border: 1px solid rgba(128, 128, 128, 0.25);
        border-radius: 8px;
        background: var(--secondary-background-color);
        text-align: center;
    }

    .surf-score-value {
        font-size: 3.5rem;
        font-weight: 700;
        line-height: 1;
    }

    .surf-score-quality {
        margin-top: 0.75rem;
        font-weight: 600;
    }

    .surf-score-label {
        margin-top: 0.35rem;
        color: var(--text-color);
        opacity: 0.7;
    }

    .score-factor-row {
        display: flex;
        justify-content: space-between;
        gap: 0.75rem;
        padding: 0.55rem 0;
        border-bottom: 1px solid rgba(128, 128, 128, 0.2);
    }

    .score-factor-row:last-child {
        border-bottom: 0;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# QUALITY LABELS
# ============================================================

QUALITY_EMOJI = {
    "POOR": "🔴",
    "FAIR": "🟠",
    "GOOD": "🟡",
    "VERY_GOOD": "🔵",
    "EXCELLENT": "🟢",
}


QUALITY_LABEL = {
    "POOR": "Poor",
    "FAIR": "Fair",
    "GOOD": "Good",
    "VERY_GOOD": "Very Good",
    "EXCELLENT": "Excellent",
}


def quality_display(quality):

    if pd.isna(quality):
        return "⚪ No data"

    quality = str(quality).upper()

    emoji = QUALITY_EMOJI.get(quality, "⚪")
    label = QUALITY_LABEL.get(quality, quality)

    return f"{emoji} {label}"


# ============================================================
# LOAD DATA
# ============================================================

@st.cache_data(ttl=900)
def load_surf_data():

    engine = get_engine()

    query = """
        SELECT
            spot_id,
            spot_name,
            timezone,
            observation_time,
            local_observation_time,
            local_date,

            wave_height_m,
            wave_period_s,
            wave_direction_deg,

            swell_height_m,
            swell_period_s,
            swell_direction_deg,

            wind_speed_kmh,
            wind_gusts_kmh,
            wind_condition,
            wind_index,
            wind_speed_index,
            wind_direction_index,

            swell_index,
            swell_height_index,
            swell_period_index,
            calculated_swell_direction_index,
            tide_index,

            surf_index,
            surf_quality_band,

            sea_surface_temperature_c,

            tide_phase,
            water_level_m,

            is_daylight,
            is_surfable_light

        FROM analytics.fct_surf_hourly

        ORDER BY
            spot_name,
            observation_time
    """

    df = pd.read_sql(query, engine)

    # Database timestamps are UTC
    df["observation_time"] = pd.to_datetime(
        df["observation_time"],
        utc=True
    )
    df["local_observation_time"] = pd.to_datetime(
        df["local_observation_time"]
    )

    return df


df = load_surf_data()


if df.empty:
    st.warning("No surf forecast data available.")
    st.stop()


# ============================================================
# HEADER
# ============================================================

st.title("🏄 Surf Forecast")

st.caption(
    "Hourly surf conditions based on weather, wave, swell and wind data."
)


# ============================================================
# SPOT FILTER
# ============================================================

spots = sorted(
    df["spot_name"]
    .dropna()
    .unique()
)


col_spot, col_date = st.columns([1, 1])


with col_spot:

    selected_spot = st.selectbox(
        "Spot",
        spots
    )


# ============================================================
# SPOT DATA + TIMEZONE
# ============================================================

spot_df = df[
    df["spot_name"] == selected_spot
].copy()


spot_timezone = spot_df["timezone"].iloc[0]


# ============================================================
# DATE FILTER
# ============================================================

available_dates = sorted(
    spot_df["local_date"]
    .dropna()
    .unique()
)


with col_date:

    selected_date = st.selectbox(
        "Day",
        available_dates,
        format_func=lambda x: x.strftime("%A %d %B %Y")
    )


# ============================================================
# SELECT LOCAL DAY
# ============================================================

day_df = spot_df[
    spot_df["local_date"] == selected_date
].copy()


# ============================================================
# SURFABLE HOURS ONLY
# ============================================================

surfable_df = day_df[
    day_df["is_surfable_light"] == True
].copy()


if surfable_df.empty:

    st.warning(
        "No surfable hours are available for this day."
    )

    st.stop()


# ============================================================
# SORT BY LOCAL TIME
# ============================================================

surfable_df = surfable_df.sort_values(
    "local_observation_time"
).reset_index(drop=True)


# ============================================================
# DAILY SURF SUMMARY
# ============================================================

daily_surf_index = (
    surfable_df["surf_index"]
    .mean()
)


best_row = surfable_df.loc[
    surfable_df["surf_index"].idxmax()
]


daily_quality = best_row[
    "surf_quality_band"
]


# ============================================================
# TOP SUMMARY
# ============================================================

st.markdown("---")

summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)


with summary_col1:

    st.metric(
        "Daily Surf Index",
        f"{daily_surf_index:.0f}/100"
    )


with summary_col2:

    st.metric(
        "Overall Quality",
        quality_display(daily_quality)
    )


with summary_col3:

    best_time = best_row[
        "local_observation_time"
    ].strftime("%H:%M")

    st.metric(
        "Best Time",
        best_time
    )


with summary_col4:

    st.metric(
        "Best Surf Index",
        f"{best_row['surf_index']:.0f}/100"
    )


# ============================================================
# SURF CONDITIONS
# ============================================================

st.markdown("## 🌊 Surf Conditions")

st.caption(
    f"Surfable daylight hours · {spot_timezone}"
)


# ============================================================
# WAVE + SWELL
# ============================================================

fig_waves = go.Figure()


fig_waves.add_trace(
    go.Scatter(
        x=surfable_df["local_observation_time"],
        y=surfable_df["wave_height_m"],
        mode="lines+markers",
        name="Wave height",
        line=dict(width=3),
        hovertemplate=(
            "<b>%{x|%H:%M}</b><br>"
            "Wave: %{y:.2f} m"
            "<extra></extra>"
        ),
    )
)


fig_waves.add_trace(
    go.Scatter(
        x=surfable_df["local_observation_time"],
        y=surfable_df["swell_height_m"],
        mode="lines+markers",
        name="Swell height",
        line=dict(
            width=2,
            dash="dot"
        ),
        hovertemplate=(
            "<b>%{x|%H:%M}</b><br>"
            "Swell: %{y:.2f} m"
            "<extra></extra>"
        ),
    )
)


fig_waves.update_layout(
    title="Wave & Swell Height",
    xaxis_title="Local time",
    yaxis_title="Height (m)",
    hovermode="x unified",
    height=400,
    margin=dict(
        l=20,
        r=20,
        t=60,
        b=20
    ),
)


st.plotly_chart(
    fig_waves,
    use_container_width=True
)


# ============================================================
# SURF SCORE
# ============================================================

st.markdown("## 🏄 Surf Score")

score_col, chart_col, factors_col = st.columns([1, 1.5, 1])

with score_col:

    st.markdown(
        f"""
        <div class="surf-score-card">
            <div class="surf-score-value">{daily_surf_index:.0f}</div>
            <div>/ 100</div>
            <div class="surf-score-quality">{quality_display(daily_quality)}</div>
            <div class="surf-score-label">Daily Surf Index</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


with chart_col:

    fig_index = go.Figure()

    fig_index.add_trace(
        go.Scatter(
            x=surfable_df["local_observation_time"],
            y=surfable_df["surf_index"],
            mode="lines+markers",
            name="Surf Index",
            line=dict(width=3),
            customdata=surfable_df["surf_quality_band"],
            hovertemplate=(
                "<b>%{x|%H:%M}</b><br>"
                "Surf Index: %{y:.0f}/100<br>"
                "Quality: %{customdata}"
                "<extra></extra>"
            ),
        ),
    )

    fig_index.update_layout(
        xaxis_title="Local time",
        yaxis_title="Surf Index",
        yaxis=dict(range=[0, 100]),
        hovermode="x unified",
        height=230,
        margin=dict(l=20, r=20, t=20, b=20),
    )

    st.plotly_chart(fig_index, use_container_width=True)


with factors_col:

    daily_swell_index = surfable_df["swell_index"].mean()
    daily_wind_index = surfable_df["wind_index"].mean()
    daily_tide_index = surfable_df["tide_index"].mean()
    best_time = best_row["local_observation_time"].strftime("%H:%M")

    st.caption("Key factors · daily average")
    st.markdown(
        f"""
        <div class="score-factor-row"><span>Swell Index</span><strong>{daily_swell_index:.0f} / 100</strong></div>
        <div class="score-factor-row"><span>Wind Index</span><strong>{daily_wind_index:.0f} / 100</strong></div>
        <div class="score-factor-row"><span>Tide Index</span><strong>{daily_tide_index:.0f} / 100</strong></div>
        <div class="score-factor-row"><span>Best Time</span><strong>{best_time}</strong></div>
        """,
        unsafe_allow_html=True,
    )


st.markdown(
    "**Surf Index = 60% Swell + 25% Wind + 15% Tide**  "
    "The Surf Index is a transparent 0–100 score designed to summarize "
    "how suitable the forecast conditions are for surfing at this spot. "
    "Each spot uses its own preferred swell and wind directions and spot-specific thresholds."
)


swell_col, component_wind_col, tide_col = st.columns(3)

with swell_col:

    daily_swell_height_index = surfable_df["swell_height_index"].mean()
    daily_swell_period_index = surfable_df["swell_period_index"].mean()
    daily_swell_direction_index = surfable_df[
        "calculated_swell_direction_index"
    ].mean()

    st.markdown("### 🌊 Swell")
    st.metric("Swell Index", f"{daily_swell_index:.0f} / 100")
    st.caption(
        "Swell quality combines swell height, period and direction. "
        "Swell Index = 50% height + 25% period + 25% direction."
    )
    st.caption(
        f"Height {daily_swell_height_index:.0f} · "
        f"Period {daily_swell_period_index:.0f} · "
        f"Direction {daily_swell_direction_index:.0f}"
    )

with component_wind_col:

    st.markdown("### 💨 Wind")
    st.metric("Wind Index", f"{daily_wind_index:.0f} / 100")
    st.caption(
        "Wind quality combines wind direction and wind speed. "
        "Wind Index = 60% direction + 40% speed. "
        "Poor direction and speed combinations can trigger a penalty."
    )

with tide_col:

    st.markdown("### 🌙 Tide")
    st.metric("Tide Index", f"{daily_tide_index:.0f} / 100")
    tide_phase = best_row["tide_phase"]
    tide_phase_display = (
        str(tide_phase).replace("_", " ").title()
        if pd.notna(tide_phase)
        else "Not available"
    )
    st.caption(f"Tide phase at best time: {tide_phase_display}.")
    st.caption(
        "Tide suitability is currently represented using a simplified "
        "spot-level rule. This is intentionally kept transparent in V1."
    )


with st.expander("Understanding swell conditions"):

    st.write(
        "Swell height measures the estimated height of the incoming swell. "
        "Larger is not necessarily better: each surf spot has a preferred size range."
    )
    st.write(
        "Swell period represents the time between successive wave crests. "
        "Longer-period swells generally carry more energy and interact differently "
        "with reefs, points and beaches."
    )
    st.write(
        "Swell direction indicates where the swell is coming from. Each spot has "
        "preferred directional windows based on its exposure and local geography."
    )


# ============================================================
# SURF DETAILS
# ============================================================

surf_col1, surf_col2, surf_col3, surf_col4 = st.columns(4)


with surf_col1:

    st.metric(
        "Wave",
        f"{best_row['wave_height_m']:.2f} m"
    )


with surf_col2:

    st.metric(
        "Swell",
        f"{best_row['swell_height_m']:.2f} m"
    )


with surf_col3:

    st.metric(
        "Swell Period",
        f"{best_row['swell_period_s']:.1f} s"
    )


with surf_col4:

    st.metric(
        "Water Temp.",
        f"{best_row['sea_surface_temperature_c']:.1f} °C"
    )


# ============================================================
# WIND CONDITIONS
# ============================================================

st.markdown("## 💨 Wind Conditions")

st.caption(
    "Wind quality depends on both wind direction and wind speed. A favorable "
    "offshore direction can improve wave shape, while stronger winds can "
    "deteriorate surface conditions. The resulting Wind Index contributes "
    "25% to the overall Surf Index."
)


fig_wind = go.Figure()


fig_wind.add_trace(
    go.Scatter(
        x=surfable_df["local_observation_time"],
        y=surfable_df["wind_speed_kmh"],
        mode="lines+markers",
        name="Wind",
        line=dict(width=3),
        customdata=surfable_df[
            "wind_condition"
        ],
        hovertemplate=(
            "<b>%{x|%H:%M}</b><br>"
            "Wind: %{y:.1f} km/h<br>"
            "Condition: %{customdata}"
            "<extra></extra>"
        ),
    )
)


fig_wind.add_trace(
    go.Scatter(
        x=surfable_df["local_observation_time"],
        y=surfable_df["wind_gusts_kmh"],
        mode="lines+markers",
        name="Gusts",
        line=dict(
            width=2,
            dash="dot"
        ),
        hovertemplate=(
            "<b>%{x|%H:%M}</b><br>"
            "Gusts: %{y:.1f} km/h"
            "<extra></extra>"
        ),
    )
)


fig_wind.update_layout(
    title="Wind Speed & Gusts",
    xaxis_title="Local time",
    yaxis_title="Speed (km/h)",
    hovermode="x unified",
    height=400,
    margin=dict(
        l=20,
        r=20,
        t=60,
        b=20
    ),
)


st.plotly_chart(
    fig_wind,
    use_container_width=True
)


# ============================================================
# WIND SUMMARY
# ============================================================

wind_col1, wind_col2, wind_col3 = st.columns(3)


best_wind_row = surfable_df.loc[
    surfable_df["wind_index"].idxmax()
]


with wind_col1:

    st.metric(
        "Wind Condition",
        str(
            best_wind_row["wind_condition"]
        )
        .replace("_", " ")
        .title()
    )


with wind_col2:

    st.metric(
        "Wind",
        f"{best_wind_row['wind_speed_kmh']:.1f} km/h"
    )


with wind_col3:

    st.metric(
        "Wind Index",
        f"{best_wind_row['wind_index']:.0f}/100"
    )


# ============================================================
# METHODOLOGY
# ============================================================

st.markdown("## 📊 Methodology")
st.caption(
    "Open-Meteo → Python ingestion → PostgreSQL RAW → dbt transformations "
    "→ Spot-specific scoring → fct_surf_hourly → Streamlit"
)

method_data_col, method_scoring_col, method_engineering_col = st.columns(3)

with method_data_col:
    st.markdown("### Data")
    st.caption(
        "Hourly weather and marine forecast data are collected from Open-Meteo "
        "and transformed through a PostgreSQL + dbt pipeline."
    )

with method_scoring_col:
    st.markdown("### Scoring")
    st.caption(
        "Surf conditions are evaluated using transparent, spot-specific rules "
        "based on swell height, period, direction, wind and tide."
    )

with method_engineering_col:
    st.markdown("### Engineering")
    st.caption(
        "The pipeline separates ingestion, storage, transformation and "
        "presentation layers, making the analytical model reproducible and maintainable."
    )

st.markdown("### Model limitations")
st.caption(
    "The Surf Index is an interpretable heuristic and should not be considered "
    "an exact prediction of surf quality. It does not currently model detailed "
    "bathymetry, wave refraction, surf spot selection, wave consistency or real-time "
    "observations. These limitations are intentional: the objective is to provide "
    "a transparent analytical model built on publicly available forecast data."
)


# HOURLY TABLE
# ============================================================

with st.expander("View hourly forecast"):

    display_df = surfable_df[
        [
            "local_observation_time",
            "surf_index",
            "surf_quality_band",
            "wave_height_m",
            "swell_height_m",
            "swell_period_s",
            "wind_speed_kmh",
            "wind_gusts_kmh",
            "wind_condition",
            "wind_index",
            "tide_phase",
        ]
    ].copy()


    display_df["local_observation_time"] = (
        display_df["local_observation_time"]
        .dt.strftime("%H:%M")
    )


    display_df.columns = [
        "Local time",
        "Surf Index",
        "Quality",
        "Wave (m)",
        "Swell (m)",
        "Swell Period (s)",
        "Wind (km/h)",
        "Gusts (km/h)",
        "Wind Condition",
        "Wind Index",
        "Tide",
    ]


    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True
    )
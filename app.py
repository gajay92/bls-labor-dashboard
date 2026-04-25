"""
app.py
------
Streamlit dashboard for U.S. Labor Market Statistics.
Reads from data/bls_data.csv — data is pre-collected by collect_data.py
and updated monthly via GitHub Actions. The app never calls the BLS API directly.
Features:

  - minor changes on the filter and metric cards
  - Multi-series comparison using normalized index (base = 100)
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os

#Page Config
st.set_page_config(
    page_title="U.S. Labor Market Dashboard",
    layout="wide",
)

#Load Data

DATA_PATH = "data/bls_data.csv"

@st.cache_data
def load_data():
    """Load and return the BLS dataset. Cached so it only reads once per session."""
    if not os.path.exists(DATA_PATH):
        return pd.DataFrame()
    df = pd.read_csv(DATA_PATH, parse_dates=["date"])
    df.sort_values("date", inplace=True)
    return df

df = load_data()

#Header

st.title("U.S. Labor Market Dashboard")
st.markdown(
    "Data sourced from the Bureau of Labor Statistics (BLS) Public API. "
    "Updated automatically each month via GitHub Actions."
)
st.divider()

# Filter against missing data file
if df.empty:
    st.error("No data found. Please run `collect_data.py` first to populate `data/bls_data.csv`.")
    st.stop()

#Sidebar code

st.sidebar.header("Controls")

# single series or compare choose selector
mode = st.sidebar.radio(
    "View Mode",
    ["Single Series", "Compare Trends"],
    help="Single Series: deep dive into one indicator. Compare Trends: overlay multiple series on a normalized chart."
)
all_series = df["series_name"].unique().tolist()

# Date range slider used on both options
min_date = df["date"].min().to_pydatetime()
max_date = df["date"].max().to_pydatetime()

start_date, end_date = st.sidebar.slider(
    "Date Range",
    min_value=min_date,
    max_value=max_date,
    value=(min_date, max_date),
    format="MMM YYYY",
)

st.sidebar.divider()
st.sidebar.caption(
    f"Data last updated: **{max_date.strftime('%B %Y')}**\n\n"
    "Source: [BLS Public Data API](https://www.bls.gov/developers/home.htm)"
)

#Filter Data
#Headline Metric Cards

st.subheader("Latest Readings (All Series)")

cols = st.columns(3)
for i, series_name in enumerate(all_series):
    series_df = df[df["series_name"] == series_name]
    if series_df.empty:
        continue
    latest = series_df.sort_values("date").iloc[-1]
    prev   = series_df.sort_values("date").iloc[-2] if len(series_df) > 1 else latest

    unit   = latest["unit"]
    value  = latest["value"]
    delta  = value - prev["value"]

    if "Percent" in unit:
        display_val   = f"{value:.1f}%"
        display_delta = f"{delta:+.1f}%"
    elif "Dollar" in unit:
        display_val   = f"${value:.2f}"
        display_delta = f"{delta:+.2f}"
    else:
        display_val   = f"{value:,.0f}K"
        display_delta = f"{delta:+,.0f}K"

    with cols[i % 3]:
        st.metric(
            label=series_name,
            value=display_val,
            delta=display_delta,
            delta_color="normal",
        )

st.divider()

# ── MODE 1: Single Series ─────────────────────────────────────────────────────

if mode == "Single Series":

    selected_series = st.sidebar.selectbox("Select a Series", all_series)

    mask = (
        (df["series_name"] == selected_series) &
        (df["date"] >= start_date) &
        (df["date"] <= end_date)
    )
    filtered = df[mask].copy()

    st.subheader(f"📈 {selected_series} Over Time")

    unit = filtered["unit"].iloc[0] if not filtered.empty else ""

    if filtered.empty:
        st.warning("No data available for the selected series and date range.")
    else:
        fig = px.line(
            filtered,
            x="date",
            y="value",
            labels={"date": "Date", "value": unit},
            markers=True,
            color_discrete_sequence=["#1f77b4"],
        )
        fig.update_layout(
            xaxis_title="Date",
            yaxis_title=unit,
            hovermode="x unified",
            plot_bgcolor="white",
            yaxis=dict(gridcolor="#eeeeee"),
            xaxis=dict(gridcolor="#eeeeee"),
        )
        st.plotly_chart(fig, use_container_width=True)

    st.subheader(" Recent Data")
    if not filtered.empty:
        recent = (
            filtered.sort_values("date", ascending=False)
            .head(12)[["date", "value", "unit"]]
            .copy()
        )
        recent["date"] = recent["date"].dt.strftime("%B %Y")
        recent.columns = ["Month", "Value", "Unit"]
        recent.reset_index(drop=True, inplace=True)
        st.dataframe(recent, use_container_width=True, hide_index=True)

# ── MODE 2: Compare Trends ────────────────────────────────────────────────────

elif mode == "Compare Trends":

    selected_compare = st.sidebar.multiselect(
        "Select Series to Compare",
        all_series,
        default=all_series[:3],
        help="Select 2 or more series to compare on a normalized chart."
    )

    st.subheader(" Compare Trends Across Series")

    st.info(
        "**How to read this chart:** Each series is normalized to an index where its "
        "first value in the selected date range = 100. This allows series with different "
        "units (percent, dollars, thousands) to be compared on the same scale. "
        "A value of 110 means that series has grown 10% from its starting point."
    )

    if len(selected_compare) < 2:
        st.warning("Please select at least 2 series to compare.")
    else:
        fig = go.Figure()

        for series_name in selected_compare:
            mask = (
                (df["series_name"] == series_name) &
                (df["date"] >= start_date) &
                (df["date"] <= end_date)
            )
            series_data = df[mask].copy().sort_values("date")

            if series_data.empty or series_data["value"].dropna().empty:
                continue

            # Normalize: first non-null value = 100
            first_val = series_data["value"].dropna().iloc[0]
            series_data["normalized"] = (series_data["value"] / first_val) * 100

            fig.add_trace(go.Scatter(
                x=series_data["date"],
                y=series_data["normalized"],
                mode="lines+markers",
                name=series_name,
                hovertemplate=(
                    f"<b>{series_name}</b><br>"
                    "Date: %{x|%B %Y}<br>"
                    "Index: %{y:.1f}<br>"
                    f"(Base = {first_val:,.2f} {series_data['unit'].iloc[0]})"
                    "<extra></extra>"
                )
            ))

        fig.update_layout(
            xaxis_title="Date",
            yaxis_title="Index (Start of Period = 100)",
            hovermode="x unified",
            plot_bgcolor="white",
            yaxis=dict(gridcolor="#eeeeee"),
            xaxis=dict(gridcolor="#eeeeee"),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )

        # Add a reference line at 100
        fig.add_hline(
            y=100,
            line_dash="dash",
            line_color="gray",
            annotation_text="Base (Start of Period)",
            annotation_position="bottom right"
        )

        st.plotly_chart(fig, use_container_width=True)

        # Show a summary table of % change for each series
        st.subheader("📋 Change Summary")
        summary_rows = []
        for series_name in selected_compare:
            mask = (
                (df["series_name"] == series_name) &
                (df["date"] >= start_date) &
                (df["date"] <= end_date)
            )
            series_data = df[mask].copy().sort_values("date").dropna(subset=["value"])
            if len(series_data) < 2:
                continue
            first_val = series_data["value"].iloc[0]
            last_val  = series_data["value"].iloc[-1]
            pct_change = ((last_val - first_val) / first_val) * 100
            unit = series_data["unit"].iloc[0]
            summary_rows.append({
                "Series": series_name,
                "Start Value": f"{first_val:,.2f} {unit}",
                "End Value": f"{last_val:,.2f} {unit}",
                "Change (%)": f"{pct_change:+.1f}%",
            })

        if summary_rows:
            summary_df = pd.DataFrame(summary_rows)
            st.dataframe(summary_df, use_container_width=True, hide_index=True)
#Footer

st.divider()
st.caption(
    "Econ 8320 — Tools for Data Analysis | "
    "Data: Bureau of Labor Statistics | "
    "Built with Streamlit & Plotly"
)

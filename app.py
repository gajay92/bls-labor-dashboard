"""
app.py
------
Streamlit dashboard for U.S. Labor Market Statistics.
Reads from data/bls_data.csv — data is pre-collected by collect_data.py
and updated monthly via GitHub Actions. The app never calls the BLS API directly.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import os

#Page Config
st.set_page_config(
    page_title="U.S. Labor Market Dashboard",
    page_icon="📊",
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
    "Data sourced from the **Bureau of Labor Statistics (BLS) Public API. "
    "Updated automatically each month via GitHub Actions."
)
st.divider()

# Filter against missing data file
if df.empty:
    st.error("No data found. Please run `collect_data.py` first to populate `data/bls_data.csv`.")
    st.stop()

#Sidebar code

st.sidebar.header("Controls")

# Series selector
all_series = df["series_name"].unique().tolist()
selected_series = st.sidebar.selectbox("Select a Series", all_series)

# Date range slider
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

#Filter to selected series and date range
mask = (
    (df["series_name"] == selected_series) &
    (df["date"] >= start_date) &
    (df["date"] <= end_date)
)
filtered = df[mask].copy()

#Headline Metric Cards

st.subheader("Latest Readings (All Series)")

# Showing only one metric card per series
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

    # Format based on unit type
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

#Line Chart

st.subheader(f"{selected_series} Over Time")

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

#Recent Data Table

st.subheader("Recent Data")

if not filtered.empty:
    # Show the 12 most recent months in a clean table
    recent = (
        filtered.sort_values("date", ascending=False)
        .head(12)[["date", "value", "unit"]]
        .copy()
    )
    recent["date"] = recent["date"].dt.strftime("%B %Y")
    recent.columns = ["Month", "Value", "Unit"]
    recent.reset_index(drop=True, inplace=True)
    st.dataframe(recent, use_container_width=True, hide_index=True)
else:
    st.info("No recent data to display.")

#Footer

st.divider()
st.caption(
    "Econ 8320 — Tools for Data Analysis | "
    "Data: Bureau of Labor Statistics | "
    "Built with Streamlit & Plotly"
)

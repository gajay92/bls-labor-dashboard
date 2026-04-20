"""
collect_data.py
---------------
Fetches labor statistics from the BLS Public API and saves them to data/bls_data.csv.
Run this script once to collect historical data, then monthly via GitHub Actions.

BLS Series collected:
    - CES0000000001  : Total Nonfarm Payroll Employment (thousands)
    - LNS14000000    : Unemployment Rate (%)
    - LNS11300000    : Labor Force Participation Rate (%)
    - CES0500000003  : Average Hourly Earnings, All Employees ($)
    - JTS000000000000000JOL : Job Openings, Total Nonfarm (thousands)
    - LNS13008636    : Long-Term Unemployment, 27 Weeks & Over (thousands)
"""

import requests
import json
import pandas as pd
import os
from datetime import datetime

# ── Configuration ────────────────────────────────────────────────────────────

API_KEY = "f623fc0710be489ea9d5f7986b0b8797"
API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
OUTPUT_PATH = "data/bls_data.csv"

# Series IDs mapped to human-readable names and units
SERIES = {
    "CES0000000001":            ("Total Nonfarm Payroll",           "Thousands of Jobs"),
    "LNS14000000":              ("Unemployment Rate",                "Percent"),
    "LNS11300000":              ("Labor Force Participation Rate",   "Percent"),
    "CES0500000003":            ("Average Hourly Earnings",          "Dollars"),
    "JTS000000000000000JOL":    ("Job Openings",                     "Thousands"),
    "LNS13008636":              ("Long-Term Unemployment (27+ wks)", "Thousands"),
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def fetch_series(series_ids: list, start_year: str, end_year: str) -> dict:
    """
    Call the BLS API for a list of series IDs over the given year range.
    Returns the raw JSON response.
    """
    payload = {
        "seriesid": series_ids,
        "startyear": start_year,
        "endyear": end_year,
        "registrationkey": API_KEY,
    }
    headers = {"Content-Type": "application/json"}
    response = requests.post(API_URL, json=payload, headers=headers)
    response.raise_for_status()
    return response.json()


def parse_response(raw: dict) -> pd.DataFrame:
    """
    Parse the BLS API JSON response into a tidy DataFrame with columns:
    series_id, series_name, unit, date, value
    """
    rows = []
    for series in raw.get("Results", {}).get("series", []):
        sid = series["seriesID"]
        name, unit = SERIES.get(sid, (sid, ""))
        for entry in series.get("data", []):
            # Skip annual summaries (period "M13")
            if entry["period"] == "M13":
                continue
            # Convert "M01"–"M12" to month number
            month_num = int(entry["period"].replace("M", ""))
            date = pd.Timestamp(year=int(entry["year"]), month=month_num, day=1)
            rows.append({
                "series_id":   sid,
                "series_name": name,
                "unit":        unit,
                "date":        date,
                "value":       float(entry["value"].replace(",", "")) if entry["value"] != "-" else None,
            })
    return pd.DataFrame(rows)


def load_existing(path: str) -> pd.DataFrame:
    """Load existing CSV if it exists, otherwise return an empty DataFrame."""
    if os.path.exists(path):
        df = pd.read_csv(path, parse_dates=["date"])
        print(f"Loaded {len(df)} existing rows from {path}")
        return df
    print("No existing data found — starting fresh.")
    return pd.DataFrame()


def save_data(df: pd.DataFrame, path: str):
    """Save DataFrame to CSV, creating directories as needed."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_csv(path, index=False)
    print(f"Saved {len(df)} rows to {path}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    current_year = datetime.now().year
    series_ids = list(SERIES.keys())

    existing_df = load_existing(OUTPUT_PATH)

    if existing_df.empty:
        # last 3 years of history
        start_year = str(current_year - 3)
        print(f"First run — collecting data from {start_year} to {current_year}...")
    else:
        # Monthly update
        start_year = str(current_year - 1)
        print(f"Monthly update — fetching {start_year} to {current_year}...")

    raw = fetch_series(series_ids, start_year, str(current_year))

    if raw.get("status") != "REQUEST_SUCCEEDED":
        print("API Error:", raw.get("message", "Unknown error"))
        return

    new_df = parse_response(raw)
    print(f"Fetched {len(new_df)} rows from BLS API")

    combined = pd.concat([existing_df, new_df], ignore_index=True)
    combined.drop_duplicates(subset=["series_id", "date"], keep="last", inplace=True)
    combined.sort_values(["series_id", "date"], inplace=True)

    save_data(combined, OUTPUT_PATH)
    print("Done!")

if __name__ == "__main__":
    main()

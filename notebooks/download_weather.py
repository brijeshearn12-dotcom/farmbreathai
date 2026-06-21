import requests
import pandas as pd
import os

# Districts with coordinates
districts = [
    {"name": "Amritsar, Punjab", "lat": 31.63, "lon": 74.87},
    {"name": "Ludhiana, Punjab", "lat": 30.90, "lon": 75.85},
    {"name": "Karnal, Haryana", "lat": 29.68, "lon": 76.99},
    {"name": "Hisar, Haryana", "lat": 29.15, "lon": 75.72},
    {"name": "Meerut, UP", "lat": 28.98, "lon": 77.70},
]

START_DATE = "2021-01-01"
END_DATE = "2025-12-31"

VARIABLES = [
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
    "windspeed_10m_max",
    "relative_humidity_2m_mean",
]

BASE_URL = "https://archive-api.open-meteo.com/v1/archive"

all_dfs = []

for district in districts:
    print(f"Fetching data for {district['name']}...")

    params = {
        "latitude": district["lat"],
        "longitude": district["lon"],
        "start_date": START_DATE,
        "end_date": END_DATE,
        "daily": ",".join(VARIABLES),
        "timezone": "Asia/Kolkata",
    }

    try:
        response = requests.get(BASE_URL, params=params, timeout=60)
        response.raise_for_status()
        data = response.json()

        daily = data.get("daily", {})
        if not daily or "time" not in daily:
            print(f"  No data returned for {district['name']}, skipping.")
            continue

        df = pd.DataFrame(daily)
        df["district"] = district["name"]
        df.rename(columns={"time": "date"}, inplace=True)

        all_dfs.append(df)
        print(f"  Got {len(df)} rows for {district['name']}")

    except requests.exceptions.RequestException as e:
        print(f"  ERROR fetching {district['name']}: {e}")
    except Exception as e:
        print(f"  Unexpected error for {district['name']}: {e}")

if not all_dfs:
    print("\nNo data was fetched. Exiting.")
else:
    # Combine all districts
    combined_df = pd.concat(all_dfs, ignore_index=True)

    # Reorder columns: district, date, then the rest
    cols = ["district", "date"] + [c for c in combined_df.columns if c not in ("district", "date")]
    combined_df = combined_df[cols]

    # Save to data/weather_data.csv
    os.makedirs("data", exist_ok=True)
    output_path = os.path.join("data", "weather_data.csv")
    combined_df.to_csv(output_path, index=False)

    print(f"\n--- DONE ---")
    print(f"Total rows: {len(combined_df)}")
    print(f"Saved to: {output_path}")
    print("\nSample rows:")
    print(combined_df.head())
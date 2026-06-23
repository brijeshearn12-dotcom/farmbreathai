import pandas as pd
import numpy as np
from sklearn.neighbors import NearestNeighbors

if __name__ == "__main__":
    import os
    for path in ["data/fire_by_district.csv", "data/weather_data.csv", "data/districts.csv"]:
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Could not find '{path}'. Run from the project root directory."
            )

    # 1. Load all files
    fire      = pd.read_csv("data/fire_by_district.csv")
    weather   = pd.read_csv("data/weather_data.csv")
    districts = pd.read_csv("data/districts.csv")

    # ── Fix 1: clean weather district names ("amritsar, punjab" → "amritsar") ──
    weather['district_clean'] = (
        weather['district']
        .str.split(',').str[0]   # keep only the city part before the comma
        .str.strip()
        .str.lower()
    )

    # Parse weather date
    weather['date']  = pd.to_datetime(weather['date'])
    weather['year']  = weather['date'].dt.year
    weather['month'] = weather['date'].dt.month

    # 2. Monthly weather averages keyed on cleaned district name
    weather_monthly = (
        weather.groupby(['district_clean', 'year', 'month'])
        .agg(
            temperature_2m_max        = ('temperature_2m_max',        'mean'),
            precipitation_sum         = ('precipitation_sum',          'mean'),
            windspeed_10m_max         = ('windspeed_10m_max',         'mean'),
            relative_humidity_2m_mean = ('relative_humidity_2m_mean', 'mean'),
        )
        .reset_index()
    )

    print(f"Weather stations available: {sorted(weather_monthly['district_clean'].unique())}")

    # ── Fix 2: map every fire district to its nearest weather station by lat/lon ──
    districts['district_lower'] = districts['district_name'].str.strip().str.lower()
    weather_station_names = set(weather_monthly['district_clean'].unique())

    weather_station_coords = (
        districts[districts['district_lower'].isin(weather_station_names)]
        [['district_lower', 'latitude', 'longitude']]
        .drop_duplicates('district_lower')
        .reset_index(drop=True)
    )
    print(f"\nWeather stations with lat/lon matched: {len(weather_station_coords)}")
    print(weather_station_coords)

    # Fit nearest-neighbor on weather station coordinates
    nn = NearestNeighbors(n_neighbors=1, algorithm='ball_tree')
    nn.fit(weather_station_coords[['latitude', 'longitude']].values)

    # Get lat/lon for all fire districts from districts.csv
    fire_district_coords = (
        districts[['district_lower', 'latitude', 'longitude']]
        .drop_duplicates('district_lower')
        .reset_index(drop=True)
    )

    fire_districts_lower = fire['nearest_district'].str.strip().str.lower().unique()
    missing = set(fire_districts_lower) - set(fire_district_coords['district_lower'])
    if missing:
        print(f"\nWARNING: no lat/lon in districts.csv for: {missing}")

    fire_district_coords = fire_district_coords[
        fire_district_coords['district_lower'].isin(fire_districts_lower)
    ].reset_index(drop=True)

    # Find nearest weather station for each fire district
    _, idx = nn.kneighbors(fire_district_coords[['latitude', 'longitude']].values)
    fire_district_coords['weather_station'] = (
        weather_station_coords.loc[idx.flatten(), 'district_lower'].values
    )

    print("\nFire district → nearest weather station:")
    print(fire_district_coords[['district_lower', 'weather_station']].to_string(index=False))

    # 3. Add weather_station column to fire df, then merge with weather
    fire['_key'] = fire['nearest_district'].str.strip().str.lower()
    fire = fire.merge(
        fire_district_coords[['district_lower', 'weather_station']],
        left_on='_key', right_on='district_lower', how='left'
    ).drop(columns=['district_lower', '_key'])

    df = fire.merge(
        weather_monthly,
        left_on=['weather_station', 'year', 'month'],
        right_on=['district_clean', 'year', 'month'],
        how='left'
    ).drop(columns=['district_clean'])

    print(f"\nRows after merge: {len(df)}")
    print(f"NaN counts:\n{df.isnull().sum()}")

    # Proper numeric typing
    df['fire_count'] = df['fire_count'].astype(int)
    df['year']       = df['year'].astype(int)
    df['month']      = df['month'].astype(int)
    for col in ['temperature_2m_max', 'precipitation_sum', 'windspeed_10m_max', 'relative_humidity_2m_mean']:
        df[col] = df[col].astype(float)

    # 4a-b. Season flags
    df['is_kharif_season'] = df['month'].isin([10, 11]).astype(int)
    df['is_rabi_season']   = df['month'].isin([4, 5]).astype(int)

    # 4c. fire_risk_label
    def risk_label(count):
        if count > 100:   return 'high'
        elif count >= 20: return 'medium'
        else:             return 'low'

    df['fire_risk_label'] = df['fire_count'].apply(risk_label)

    # 4d. fire_risk_score 0-10 based on fire_count percentile
    df['fire_risk_score'] = pd.qcut(
        df['fire_count'].rank(method='first'),
        q=11, labels=False, duplicates='drop'
    ).astype(int)

    # 4e. lag_fire_count: same district + month, previous year
    df = df.sort_values(['nearest_district', 'month', 'year'])
    df['lag_fire_count'] = df.groupby(['nearest_district', 'month'])['fire_count'].shift(1)

    # 4f. wind_drought_index
    df['wind_drought_index'] = df['windspeed_10m_max'] * (1.0 / (df['precipitation_sum'] + 1))

    # 5. Drop rows with any NaN (lag year + weather gaps)
    df = df.dropna().reset_index(drop=True)
    df['lag_fire_count'] = df['lag_fire_count'].astype(int)

    # 6. Save
    df.to_csv("data/master_dataset.csv", index=False)

    # 7. Summary
    print(f"\nTotal rows: {len(df)}")
    print(f"\nColumns: {list(df.columns)}")
    print(f"\nClass distribution:\n{df['fire_risk_label'].value_counts()}")
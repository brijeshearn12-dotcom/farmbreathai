import pandas as pd
from sklearn.neighbors import NearestNeighbors
import numpy as np

if __name__ == "__main__":
    import os
    for path in ["data/fire_data_clean.csv", "data/districts.csv"]:
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Could not find '{path}'. Run from the project root directory."
            )

    # 1. Load data
    fires = pd.read_csv("data/fire_data_clean.csv")
    districts = pd.read_csv("data/districts.csv")

    # 2. Fit nearest-neighbor model on district coordinates
    district_coords = districts[['latitude', 'longitude']].values
    nn = NearestNeighbors(n_neighbors=1, algorithm='ball_tree').fit(district_coords)

    fire_coords = fires[['latitude', 'longitude']].values

    # Find nearest district for each fire (in batches with progress print)
    nearest_idx = np.empty(len(fires), dtype=int)
    batch_size = 10000
    for start in range(0, len(fires), batch_size):
        end = min(start + batch_size, len(fires))
        _, idx = nn.kneighbors(fire_coords[start:end])
        nearest_idx[start:end] = idx.flatten()
        print(f"Processed {end} / {len(fires)} rows")

    # 3. Add nearest district name and state
    fires['nearest_district'] = districts['district_name'].values[nearest_idx]
    fires['district_state'] = districts['state'].values[nearest_idx]

    # 4-5. Group and count
    grouped = (
        fires.groupby(['year', 'month', 'harvest_season', 'nearest_district', 'district_state'])
        .size()
        .reset_index(name='fire_count')
    )

    # 6. Save result
    grouped.to_csv("data/fire_by_district.csv", index=False)

    # 7. Top 10 districts by total fire count
    top10 = (
        fires.groupby(['nearest_district', 'district_state'])
        .size()
        .reset_index(name='fire_count')
        .sort_values('fire_count', ascending=False)
        .head(10)
    )
    print("\nTop 10 districts by total fire count:")
    print(top10.to_string(index=False))
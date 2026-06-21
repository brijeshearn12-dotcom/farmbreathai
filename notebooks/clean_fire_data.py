import pandas as pd

# 1. Load data
df = pd.read_csv("data/fire_data.csv")
original_rows = len(df)

# 2-3. Filter to Punjab+Haryana+UP bounding box
df = df[(df['latitude'].between(27.0, 32.5)) & (df['longitude'].between(73.0, 81.0))]

# 4. Convert acq_date to datetime
df['acq_date'] = pd.to_datetime(df['acq_date'])

# 8. Extract year and month
df['year'] = df['acq_date'].dt.year
df['month'] = df['acq_date'].dt.month

# 5. Filter to harvest season months
df = df[df['month'].isin([10, 11, 4, 5])]

# 6. Filter by confidence
df = df[df['confidence'] >= 50]

# 7. Add harvest_season label
df['harvest_season'] = df['month'].map({10: 'kharif', 11: 'kharif', 4: 'rabi', 5: 'rabi'})

filtered_rows = len(df)

# 9. Save cleaned data
df.to_csv("data/fire_data_clean.csv", index=False)

# 10. Print summary stats
print(f"Original rows: {original_rows}")
print(f"Filtered rows: {filtered_rows}")
print("\nRows per year:")
print(df['year'].value_counts().sort_index())
print("\nRows per month:")
print(df['month'].value_counts().sort_index())
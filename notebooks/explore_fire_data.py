import pandas as pd
import glob
import os

if __name__ == "__main__":
    # Folder containing your CSVs (change if your folder has a different name)
    data_folder = "."

    # Find all CSV files, including any in subfolders
    csv_files = glob.glob(os.path.join(data_folder, "**", "*.csv"), recursive=True)

    print(f"Found {len(csv_files)} CSV files")

    df_list = []
    for file in csv_files:
        try:
            df = pd.read_csv(file)
            df_list.append(df)
        except Exception as e:
            print(f"Skipped {file}: {e}")

    if not df_list:
        print("No CSV files could be loaded. Exiting.")
    else:
        # Combine everything
        df = pd.concat(df_list, ignore_index=True)

        # Save combined file
        df.to_csv("india_modis_fires_2021_2025.csv", index=False)

        # Convert date column (only if present)
        if 'acq_date' in df.columns:
            df['acq_date'] = pd.to_datetime(df['acq_date'])

        # Print summary
        print("\n--- SUMMARY ---")
        print(f"Columns: {df.columns.tolist()}")
        print(f"Total rows: {len(df)}")
        if 'acq_date' in df.columns:
            print(f"Date range: {df['acq_date'].min()} to {df['acq_date'].max()}")
        print("\nSaved as: india_modis_fires_2021_2025.csv")
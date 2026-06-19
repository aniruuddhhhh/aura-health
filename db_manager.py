"""
CSV files expected path: data/ folder:
- filtered_heartrate_seconds_merged.csv  (Id, Time, Value)
- filtered_dailyActivity_merged.csv      (Id, ActivityDate, TotalSteps, Calories, ...)
- filtered_sleepDay_merged.csv           (Id, SleepDay, TotalMinutesAsleep, ...)
"""
import sqlite3
import pandas as pd
import os
import time

DB_NAME = "aura_health.db"

# File mapping: table_name -> CSV path
FILES_TO_LOAD = {
    "heart_rate":       "data/filtered_heartrate_seconds_merged.csv",
    "daily_activity":   "data/filtered_dailyActivity_merged.csv",
    "sleep_logs":       "data/filtered_sleepDay_merged.csv",
}

# Columns that contain dates/times
TIME_COLS = ["Time", "ActivityDate", "SleepDay", "ActivityMinute", "ActivityHour"]


def build_numerical_vault() -> None:
    """Build SQL database from CSV files."""
    start = time.time()
    print(f"--- AURA: Building Numerical Fact-Vault ({DB_NAME}) ---")
    
    if not os.path.exists("data"):
        print("ERROR: 'data/' folder not found!")
        print("Please create it and add your CSV files:")
        for table, path in FILES_TO_LOAD.items():
            print(f"   - {path}")
        return
    
    conn = sqlite3.connect(DB_NAME)
    loaded_tables = []

    for table_name, file_path in FILES_TO_LOAD.items():
        if not os.path.exists(file_path):
            print(f"  Skipping missing file: {file_path}")
            continue
            
        print(f"  Loading {table_name} from {file_path}...")
        
        try:
            df = pd.read_csv(file_path)
            print(f"     Columns: {list(df.columns)}")
            
            date_col = next((c for c in TIME_COLS if c in df.columns), None)
            if date_col:
                df[date_col] = pd.to_datetime(df[date_col]).dt.strftime("%Y-%m-%d %H:%M:%S")
                print(f"     Standardized date column: {date_col}")
            
            df.to_sql(table_name, conn, if_exists="replace", index=False)
            print(f"  OK: {len(df):,} records -> '{table_name}'\n")
            loaded_tables.append(table_name)
            
        except Exception as e:
            print(f"  ERROR loading {file_path}: {e}\n")

    if not loaded_tables:
        print("No tables loaded. Check that your CSV files are in data/ folder.")
        conn.close()
        return

    print("Creating indexes...")
    cursor = conn.cursor()
    for cmd in [
        "CREATE INDEX IF NOT EXISTS idx_hr_time   ON heart_rate     (Time);",
        "CREATE INDEX IF NOT EXISTS idx_hr_id     ON heart_rate     (Id, Time);",
        "CREATE INDEX IF NOT EXISTS idx_sleep_day ON sleep_logs     (SleepDay);",
        "CREATE INDEX IF NOT EXISTS idx_act_date  ON daily_activity (ActivityDate);",
    ]:
        try:
            cursor.execute(cmd)
        except sqlite3.OperationalError:
            pass
    conn.commit()
    print("  Indexes created")

    print("\n--- VERIFICATION ---")
    try:
        if "heart_rate" in loaded_tables:
            cursor.execute("SELECT COUNT(*) FROM heart_rate")
            count = cursor.fetchone()[0]
            cursor.execute("SELECT MIN(Time), MAX(Time) FROM heart_rate")
            min_t, max_t = cursor.fetchone()
            cursor.execute("SELECT MAX(Value) FROM heart_rate")
            max_hr = cursor.fetchone()[0]
            
            print(f"  Heart Rate: {count:,} records")
            print(f"    Date range: {min_t} to {max_t}")
            print(f"    Max HR: {max_hr} BPM")
        
        if "sleep_logs" in loaded_tables:
            cursor.execute("SELECT COUNT(*) FROM sleep_logs")
            count = cursor.fetchone()[0]
            print(f"  Sleep Logs: {count:,} records")
        
        if "daily_activity" in loaded_tables:
            cursor.execute("SELECT COUNT(*) FROM daily_activity")
            count = cursor.fetchone()[0]
            print(f"  Daily Activity: {count:,} records")
        
        try:
            cursor.execute("SELECT DISTINCT Id FROM heart_rate LIMIT 5")
            user_ids = [row[0] for row in cursor.fetchall()]
            print(f"  User IDs found: {user_ids}")
        except:
            pass
            
    except Exception as e:
        print(f"  Verification error: {e}")

    conn.close()
    print(f"\nDatabase ready! Time: {time.time() - start:.2f}s")
    print(f"Loaded {len(loaded_tables)} table(s): {', '.join(loaded_tables)}")


if __name__ == "__main__":
    build_numerical_vault()

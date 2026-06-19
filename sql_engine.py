"""
  - Simple templates (single date, basic aggregates)
  - Gemini for complex queries with rich few-shot examples:
    * Comparisons (date vs date)
    * Trends (over time)
    * Multi-table JOINs (sleep + heart rate correlations)
    * Time-of-day analysis (hourly patterns)
    * Weekly aggregates
    * Anomaly detection (outliers, z-scores)
"""

import sqlite3
import re
import pandas as pd

from config import CURRENT_USER_ID, SQL_DB_PATH, DEBUG_MODE
from gemini_client import call_gemini, is_gemini_available

# DATE / KEYWORD DETECTION

def parse_date(user_input: str) -> str:
    match = re.search(r'(april|may)\s+(\d+)', user_input.lower())
    if match:
        month = 4 if match.group(1) == "april" else 5
        day = int(match.group(2))
        return f"2016-{month:02d}-{day:02d}"
    return None

def parse_multiple_dates(user_input: str) -> list:
    matches = re.findall(r'(april|may)\s+(\d+)', user_input.lower())
    dates = []
    for month_name, day in matches:
        month = 4 if month_name == "april" else 5
        day = int(day)
        dates.append(f"2016-{month:02d}-{day:02d}")
    return dates

def detect_aggregate(query: str) -> str:
    q = query.lower()
    if any(w in q for w in ["average", "avg", "mean"]):
        return "AVG"
    if any(w in q for w in ["maximum", "highest", "peak", "max"]):
        return "MAX"
    if any(w in q for w in ["minimum", "lowest", "min"]):
        return "MIN"
    if any(w in q for w in ["total", "sum"]):
        return "SUM"
    if any(w in q for w in ["count", "how many"]):
        return "COUNT"
    return None

def detect_query_pattern(query: str) -> str:
    """
    Detect specific complex query patterns for better Gemini prompting.
    Returns: comparison, trend, join, hourly, weekly, anomaly, or simple
    """
    q = query.lower()
    
    if any(p in q for p in [
        "slept poorly and", "sleep and heart", "both", "as well as",
        "while", "during", "correlate", "correlation",
        "when i was", "when my", "days when",
    ]):
        return "join"
    
    if any(p in q for p in [
        "by hour", "hour of day", "hourly", "by time",
        "morning vs", "afternoon vs", "evening vs",
        "what time", "time of day", "throughout the day",
    ]):
        return "hourly"
    
    if any(p in q for p in [
        "per week", "weekly", "by week", "each week",
        "weekend vs", "weekday", "every week",
    ]):
        return "weekly"
    
    if any(p in q for p in [
        "outlier", "outliers", "unusual", "abnormal",
        "anomaly", "anomalies", "spike", "spikes",
        "stand out", "different from average", "extreme",
    ]):
        return "anomaly"
    
    if any(p in q for p in [
        "compare", "comparison", "vs ", "versus",
        "difference between", "better than", "worse than",
    ]):
        return "comparison"
    
    if any(p in q for p in [
        "trend", "trends", "pattern", "over time",
        "throughout", "across the", "monthly",
    ]):
        return "trend"
    
    return "simple"


def is_complex_query(query: str) -> bool:
    """Complex = anything not 'simple' pattern."""
    pattern = detect_query_pattern(query)
    return pattern != "simple"

# SIMPLE TEMPLATES

def get_template_sql(user_query: str, date: str) -> str:
    if is_complex_query(user_query):
        return None
    
    user_lower = user_query.lower()
    agg_func = detect_aggregate(user_query)
    
    # HEART RATE
    if "heart" in user_lower or "hr" in user_lower:
        if agg_func and date:
            if agg_func == "AVG":
                return f"""SELECT 
                              ROUND(AVG(Value), 1) AS Average_HR,
                              MIN(Value) AS Min_HR,
                              MAX(Value) AS Max_HR,
                              COUNT(*) AS Total_Readings
                          FROM heart_rate 
                          WHERE Id = {CURRENT_USER_ID} 
                          AND Time LIKE '{date}%'"""
            elif agg_func == "MAX":
                return f"""SELECT MAX(Value) AS Max_HR, ROUND(AVG(Value), 1) AS Avg_HR
                          FROM heart_rate WHERE Id = {CURRENT_USER_ID} 
                          AND Time LIKE '{date}%'"""
            elif agg_func == "MIN":
                return f"""SELECT MIN(Value) AS Min_HR, ROUND(AVG(Value), 1) AS Avg_HR
                          FROM heart_rate WHERE Id = {CURRENT_USER_ID} 
                          AND Time LIKE '{date}%'"""
        
        if date and not agg_func:
            return f"""SELECT Time, Value 
                      FROM heart_rate 
                      WHERE Id = {CURRENT_USER_ID} 
                      AND Time LIKE '{date}%' 
                      ORDER BY Value DESC 
                      LIMIT 20"""
        
        if "high" in user_lower or "above" in user_lower:
            return f"""SELECT Time, Value FROM heart_rate 
                      WHERE Id = {CURRENT_USER_ID} AND Value > 100 
                      ORDER BY Value DESC LIMIT 10"""
    
    # SLEEP
    if "sleep" in user_lower:
        if date:
            return f"""SELECT SleepDay, TotalMinutesAsleep, TotalTimeInBed 
                      FROM sleep_logs 
                      WHERE Id = {CURRENT_USER_ID} 
                      AND SleepDay LIKE '{date}%'"""
        
        if "less than" in user_lower or "under" in user_lower:
            hours = re.search(r'(\d+)\s*hour', user_lower)
            if hours:
                minutes = int(hours.group(1)) * 60
                return f"""SELECT SleepDay, TotalMinutesAsleep 
                          FROM sleep_logs 
                          WHERE Id = {CURRENT_USER_ID} 
                          AND TotalMinutesAsleep < {minutes} 
                          ORDER BY TotalMinutesAsleep"""
    
    # ACTIVITY
    if "step" in user_lower or "walk" in user_lower or "active" in user_lower:
        if date:
            return f"""SELECT ActivityDate, TotalSteps, Calories,
                              VeryActiveMinutes, FairlyActiveMinutes
                      FROM daily_activity 
                      WHERE Id = {CURRENT_USER_ID} 
                      AND ActivityDate LIKE '{date}%'"""
        
        if "most" in user_lower or "highest" in user_lower:
            return f"""SELECT ActivityDate, TotalSteps, Calories
                      FROM daily_activity 
                      WHERE Id = {CURRENT_USER_ID} 
                      ORDER BY TotalSteps DESC LIMIT 10"""
    
    # CALORIES
    if ("calorie" in user_lower or "burn" in user_lower) and date:
        return f"""SELECT ActivityDate, Calories, TotalSteps
                  FROM daily_activity 
                  WHERE Id = {CURRENT_USER_ID} 
                  AND ActivityDate LIKE '{date}%'"""
    
    return None

# GEMINI SQL with PATTERN-SPECIFIC PROMPTS

# Few-shot examples organized by pattern type
PATTERN_EXAMPLES = {
    "comparison": """
COMPARISON PATTERNS:

Q: "Compare my heart rate on May 2 vs May 9"
SQL:
SELECT 
    substr(Time, 1, 10) AS Date,
    ROUND(AVG(Value), 1) AS Average_HR,
    MIN(Value) AS Min_HR,
    MAX(Value) AS Max_HR,
    COUNT(*) AS Readings
FROM heart_rate
WHERE Id = {user_id}
  AND (Time LIKE '2016-05-02%' OR Time LIKE '2016-05-09%')
GROUP BY substr(Time, 1, 10)
ORDER BY Date;

Q: "Compare my activity April 17 vs April 25"
SQL:
SELECT
    substr(ActivityDate, 1, 10) AS Date,
    TotalSteps, Calories, VeryActiveMinutes, SedentaryMinutes
FROM daily_activity
WHERE Id = {user_id}
  AND (ActivityDate LIKE '2016-04-17%' OR ActivityDate LIKE '2016-04-25%')
ORDER BY Date;
""",
    
    "trend": """
TREND PATTERNS:

Q: "Show me my sleep trend this month"
SQL:
SELECT 
    substr(SleepDay, 1, 10) AS Date,
    TotalMinutesAsleep AS Minutes_Asleep,
    ROUND(TotalMinutesAsleep / 60.0, 2) AS Hours_Asleep
FROM sleep_logs
WHERE Id = {user_id}
ORDER BY Date;

Q: "Show my steps trend"
SQL:
SELECT 
    substr(ActivityDate, 1, 10) AS Date,
    TotalSteps, Calories
FROM daily_activity
WHERE Id = {user_id}
ORDER BY Date;

Q: "Heart rate pattern over the month"
SQL:
SELECT 
    substr(Time, 1, 10) AS Date,
    ROUND(AVG(Value), 1) AS Avg_HR,
    MAX(Value) AS Peak_HR,
    COUNT(*) AS Readings
FROM heart_rate
WHERE Id = {user_id}
GROUP BY substr(Time, 1, 10)
ORDER BY Date;
""",
    
    "join": """
MULTI-TABLE JOIN PATTERNS (correlate sleep + heart rate + activity):

Q: "Days when I slept poorly AND had high heart rate"
SQL:
SELECT 
    substr(s.SleepDay, 1, 10) AS Date,
    s.TotalMinutesAsleep AS Minutes_Asleep,
    ROUND(s.TotalMinutesAsleep / 60.0, 1) AS Hours_Asleep,
    ROUND(AVG(h.Value), 1) AS Avg_HR,
    MAX(h.Value) AS Peak_HR
FROM sleep_logs s
JOIN heart_rate h 
  ON substr(s.SleepDay, 1, 10) = substr(h.Time, 1, 10)
  AND s.Id = h.Id
WHERE s.Id = {user_id}
  AND s.TotalMinutesAsleep < 420
GROUP BY substr(s.SleepDay, 1, 10), s.TotalMinutesAsleep
HAVING AVG(h.Value) > 80
ORDER BY Date;

Q: "Days when I was active and my heart rate spiked"
SQL:
SELECT 
    substr(a.ActivityDate, 1, 10) AS Date,
    a.TotalSteps,
    a.VeryActiveMinutes,
    MAX(h.Value) AS Peak_HR,
    ROUND(AVG(h.Value), 1) AS Avg_HR
FROM daily_activity a
JOIN heart_rate h 
  ON substr(a.ActivityDate, 1, 10) = substr(h.Time, 1, 10)
  AND a.Id = h.Id
WHERE a.Id = {user_id}
  AND a.TotalSteps > 7000
GROUP BY substr(a.ActivityDate, 1, 10), a.TotalSteps, a.VeryActiveMinutes
HAVING MAX(h.Value) > 100
ORDER BY Date;

Q: "Show correlation between sleep and steps"
SQL:
SELECT 
    substr(s.SleepDay, 1, 10) AS Date,
    ROUND(s.TotalMinutesAsleep / 60.0, 1) AS Hours_Asleep,
    a.TotalSteps,
    a.Calories
FROM sleep_logs s
JOIN daily_activity a 
  ON substr(s.SleepDay, 1, 10) = substr(a.ActivityDate, 1, 10)
  AND s.Id = a.Id
WHERE s.Id = {user_id}
ORDER BY Date;
""",
    
    "hourly": """
TIME-OF-DAY ANALYSIS PATTERNS:

Q: "Heart rate by hour of day"
SQL:
SELECT 
    substr(Time, 12, 2) AS Hour_of_Day,
    ROUND(AVG(Value), 1) AS Avg_HR,
    MIN(Value) AS Min_HR,
    MAX(Value) AS Max_HR,
    COUNT(*) AS Readings
FROM heart_rate
WHERE Id = {user_id}
GROUP BY substr(Time, 12, 2)
ORDER BY Hour_of_Day;

Q: "What time of day is my heart rate highest?"
SQL:
SELECT 
    substr(Time, 12, 2) AS Hour_of_Day,
    ROUND(AVG(Value), 1) AS Avg_HR,
    MAX(Value) AS Peak_HR
FROM heart_rate
WHERE Id = {user_id}
GROUP BY substr(Time, 12, 2)
ORDER BY Avg_HR DESC
LIMIT 5;

Q: "Morning vs evening heart rate"
SQL:
SELECT 
    CASE 
        WHEN CAST(substr(Time, 12, 2) AS INTEGER) < 12 THEN 'Morning'
        WHEN CAST(substr(Time, 12, 2) AS INTEGER) < 18 THEN 'Afternoon'
        ELSE 'Evening'
    END AS Time_Period,
    ROUND(AVG(Value), 1) AS Avg_HR,
    COUNT(*) AS Readings
FROM heart_rate
WHERE Id = {user_id}
GROUP BY Time_Period
ORDER BY Avg_HR DESC;
""",
    
    "weekly": """
WEEKLY AGGREGATE PATTERNS:

Q: "Average steps per week"
SQL:
SELECT 
    strftime('%Y-W%W', ActivityDate) AS Week,
    MIN(substr(ActivityDate, 1, 10)) AS Week_Start,
    MAX(substr(ActivityDate, 1, 10)) AS Week_End,
    ROUND(AVG(TotalSteps), 0) AS Avg_Daily_Steps,
    SUM(TotalSteps) AS Total_Weekly_Steps,
    ROUND(AVG(Calories), 0) AS Avg_Daily_Calories
FROM daily_activity
WHERE Id = {user_id}
GROUP BY Week
ORDER BY Week;

Q: "Average sleep per week"
SQL:
SELECT 
    strftime('%Y-W%W', SleepDay) AS Week,
    MIN(substr(SleepDay, 1, 10)) AS Week_Start,
    MAX(substr(SleepDay, 1, 10)) AS Week_End,
    ROUND(AVG(TotalMinutesAsleep) / 60.0, 2) AS Avg_Hours,
    COUNT(*) AS Nights_Tracked
FROM sleep_logs
WHERE Id = {user_id}
GROUP BY Week
ORDER BY Week;

Q: "Weekly heart rate summary"
SQL:
SELECT 
    strftime('%Y-W%W', Time) AS Week,
    ROUND(AVG(Value), 1) AS Avg_HR,
    MIN(Value) AS Min_HR,
    MAX(Value) AS Peak_HR,
    COUNT(*) AS Readings
FROM heart_rate
WHERE Id = {user_id}
GROUP BY Week
ORDER BY Week;
""",
    
    "anomaly": """
ANOMALY DETECTION PATTERNS (outliers based on stats):

Q: "Show me outlier days for heart rate"
SQL:
WITH stats AS (
    SELECT 
        AVG(Value) AS mean_hr,
        AVG(Value*Value) - AVG(Value)*AVG(Value) AS variance
    FROM heart_rate
    WHERE Id = {user_id}
),
daily AS (
    SELECT 
        substr(Time, 1, 10) AS Date,
        ROUND(AVG(Value), 1) AS Daily_Avg_HR,
        MAX(Value) AS Peak_HR
    FROM heart_rate
    WHERE Id = {user_id}
    GROUP BY substr(Time, 1, 10)
)
SELECT 
    d.Date,
    d.Daily_Avg_HR,
    d.Peak_HR,
    ROUND((d.Daily_Avg_HR - s.mean_hr), 1) AS Diff_From_Mean
FROM daily d, stats s
WHERE ABS(d.Daily_Avg_HR - s.mean_hr) > (1.5 * (s.variance * 1.0))
ORDER BY ABS(d.Daily_Avg_HR - s.mean_hr) DESC;

Q: "Unusual sleep nights"
SQL:
WITH stats AS (
    SELECT AVG(TotalMinutesAsleep) AS avg_sleep
    FROM sleep_logs
    WHERE Id = {user_id}
)
SELECT 
    substr(SleepDay, 1, 10) AS Date,
    TotalMinutesAsleep AS Minutes_Asleep,
    ROUND(TotalMinutesAsleep / 60.0, 1) AS Hours_Asleep,
    ROUND(TotalMinutesAsleep - (SELECT avg_sleep FROM stats), 0) AS Diff_From_Average
FROM sleep_logs
WHERE Id = {user_id}
  AND (TotalMinutesAsleep < (SELECT avg_sleep FROM stats) * 0.7
       OR TotalMinutesAsleep > (SELECT avg_sleep FROM stats) * 1.3)
ORDER BY ABS(TotalMinutesAsleep - (SELECT avg_sleep FROM stats)) DESC;

Q: "Days with extreme step counts"
SQL:
WITH stats AS (
    SELECT AVG(TotalSteps) AS avg_steps
    FROM daily_activity
    WHERE Id = {user_id}
)
SELECT 
    substr(ActivityDate, 1, 10) AS Date,
    TotalSteps,
    Calories,
    ROUND(TotalSteps - (SELECT avg_steps FROM stats), 0) AS Diff_From_Average
FROM daily_activity
WHERE Id = {user_id}
  AND (TotalSteps < (SELECT avg_steps FROM stats) * 0.5
       OR TotalSteps > (SELECT avg_steps FROM stats) * 1.5)
ORDER BY ABS(TotalSteps - (SELECT avg_steps FROM stats)) DESC;
""",
}

def get_gemini_sql(user_query: str) -> str:
    """Generate SQL via Gemini using pattern-specific few-shot examples."""
    if not is_gemini_available():
        if DEBUG_MODE:
            print("[SQL] Gemini unavailable for complex query")
        return None
    
    pattern = detect_query_pattern(user_query)
    
    if DEBUG_MODE:
        print(f"[SQL] Detected pattern: {pattern}")
    
    relevant_examples = ""
    if pattern in PATTERN_EXAMPLES:
        relevant_examples = PATTERN_EXAMPLES[pattern].format(user_id=CURRENT_USER_ID)
    else:
        relevant_examples = (
            PATTERN_EXAMPLES["comparison"].format(user_id=CURRENT_USER_ID) +
            PATTERN_EXAMPLES["trend"].format(user_id=CURRENT_USER_ID)
        )
    
    prompt = f"""You are an expert SQLite query generator for a health analytics database.
Generate ONLY a valid SQL query. No explanation, no markdown, no comments.

DATABASE SCHEMA

heart_rate (Id, Time, Value)
  - Time: 'YYYY-MM-DD HH:MM:SS' format
  - Use substr(Time, 1, 10) for date, substr(Time, 12, 2) for hour
  - Value: heart rate in BPM

sleep_logs (Id, SleepDay, TotalSleepRecords, TotalMinutesAsleep, TotalTimeInBed)
  - SleepDay: 'YYYY-MM-DD HH:MM:SS' format
  - TotalMinutesAsleep: integer minutes
  - <420 minutes = poor sleep (under 7 hours)
  - >480 minutes = good sleep (over 8 hours)

daily_activity (Id, ActivityDate, TotalSteps, TotalDistance,
                VeryActiveDistance, ModeratelyActiveDistance, LightActiveDistance,
                VeryActiveMinutes, FairlyActiveMinutes, LightlyActiveMinutes,
                SedentaryMinutes, Calories)
  - ActivityDate: 'YYYY-MM-DD HH:MM:SS' format
  - TotalSteps: integer

HARD CONSTRAINTS (CRITICAL):

1. ALWAYS include: WHERE Id = {CURRENT_USER_ID}
2. Date range: 2016-04-12 to 2016-05-12 (no other dates exist)
3. SELECT statements ONLY (no INSERT/UPDATE/DELETE/DROP)
4. Use ROUND(value, 1) for decimals
5. For JOIN: match on substr(date, 1, 10) AND Id
6. NEVER use dates outside 2016-04-12 to 2016-05-12


QUERY PATTERN: {pattern.upper()}

{relevant_examples}

USER QUERY

{user_query}

Generate the SQL (no markdown, no explanation, just SQL):"""
    
    response = call_gemini(prompt, temperature=0)
    
    if not response:
        return None
    
    sql = response.replace('```sql', '').replace('```', '').strip()
    
    select_idx = sql.upper().find('SELECT')
    with_idx = sql.upper().find('WITH')
    
    # Handle CTEs (WITH clauses)
    start_idx = -1
    if with_idx >= 0 and (select_idx < 0 or with_idx < select_idx):
        start_idx = with_idx
    elif select_idx >= 0:
        start_idx = select_idx
    
    if start_idx > 0:
        sql = sql[start_idx:]
    
    sql_upper = sql.upper()
    if not (sql_upper.startswith('SELECT') or sql_upper.startswith('WITH')):
        if DEBUG_MODE:
            print(f"[SQL] Invalid SQL start: {sql[:100]}")
        return None
    
    dangerous = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'TRUNCATE', 'CREATE TABLE']
    if any(d in sql_upper for d in dangerous):
        if DEBUG_MODE:
            print(f"[SQL] Dangerous SQL rejected")
        return None
    
    if str(CURRENT_USER_ID) not in sql:
        if DEBUG_MODE:
            print(f"[SQL] Missing user ID filter")
        return None
    
    return sql

# HYBRID ROUTING

def generate_sql(user_query: str, date: str = None) -> tuple[str, str]:
    if DEBUG_MODE:
        print(f"[SQL] Generating for: {user_query}")
    
    pattern = detect_query_pattern(user_query)
    
    if pattern != "simple":
        if DEBUG_MODE:
            print(f"[SQL] {pattern} query - using Gemini")
        
        gemini_sql = get_gemini_sql(user_query)
        if gemini_sql:
            if DEBUG_MODE:
                print(f"[SQL] Generated via Gemini")
            return gemini_sql, f"gemini ({pattern})"
        
        return None, "none"
    
    template_sql = get_template_sql(user_query, date)
    if template_sql:
        if DEBUG_MODE:
            print(f"[SQL] Using template")
        return template_sql, "template"
    
    if DEBUG_MODE:
        print(f"[SQL] No template match, trying Gemini fallback")
    
    gemini_sql = get_gemini_sql(user_query)
    if gemini_sql:
        return gemini_sql, "gemini (fallback)"
    
    return None, "none"

# EXECUTION

def get_nearest_dates_with_data(user_query: str, target_date: str) -> list:
    user_lower = user_query.lower()
    
    if "heart" in user_lower or "hr" in user_lower:
        table, date_col = "heart_rate", "Time"
    elif "sleep" in user_lower:
        table, date_col = "sleep_logs", "SleepDay"
    elif "step" in user_lower or "calorie" in user_lower or "activ" in user_lower:
        table, date_col = "daily_activity", "ActivityDate"
    else:
        return []
    
    conn = sqlite3.connect(SQL_DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute(f"""
            SELECT DISTINCT substr({date_col}, 1, 10) FROM {table}
            WHERE Id = ? ORDER BY 1
        """, (CURRENT_USER_ID,))
        
        all_dates = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        if not all_dates:
            return []
        
        from datetime import datetime
        target = datetime.strptime(target_date, "%Y-%m-%d")
        
        dated = []
        for d in all_dates:
            try:
                dt = datetime.strptime(d, "%Y-%m-%d")
                dated.append((d, abs((dt - target).days)))
            except:
                continue
        
        dated.sort(key=lambda x: x[1])
        return [d for d, _ in dated[:3]]
    except:
        conn.close()
        return []

def execute_sql(sql: str, user_query: str = "", target_date: str = None) -> str:
    if not sql:
        return "No SQL query to execute."
    
    conn = sqlite3.connect(SQL_DB_PATH)
    try:
        df = pd.read_sql_query(sql, conn)
        conn.close()
        
        if df.empty:
            if target_date and user_query:
                nearest = get_nearest_dates_with_data(user_query, target_date)
                if nearest:
                    return (
                        f"No data found for {target_date}. "
                        f"You have data on nearby dates: {', '.join(nearest)}. "
                        f"Try one of those instead."
                    )
            return "No data found for the specified criteria."
        
        if len(df) <= 30:
            result = df.to_string(index=False)
        else:
            result = df.head(30).to_string(index=False) + f"\n... ({len(df)-30} more rows)"
        
        if DEBUG_MODE:
            print(f"[SQL] Returned {len(df)} rows")
        
        return result
        
    except Exception as e:
        conn.close()
        if DEBUG_MODE:
            print(f"[SQL] Execution error: {e}")
        return f"Error executing query: {e}"


if __name__ == "__main__":
    print("Testing Advanced SQL Engine\n" + "="*70)
    
    test_queries = [
        # Simple
        ("Heart rate on May 9", "simple"),
        ("Average heart rate on May 2", "simple"),
        
        # Comparison
        ("Compare my heart rate on May 2 vs May 9", "comparison"),
        ("Compare my activity April 17 vs April 25", "comparison"),
        
        # Trend
        ("Show me my sleep trend", "trend"),
        ("Heart rate pattern over the month", "trend"),
        
        # JOIN (multi-table)
        ("Days when I slept poorly AND had high heart rate", "join"),
        ("Show correlation between sleep and steps", "join"),
        
        # Hourly
        ("Heart rate by hour of day", "hourly"),
        ("What time of day is my heart rate highest?", "hourly"),
        ("Morning vs evening heart rate", "hourly"),
        
        # Weekly
        ("Average steps per week", "weekly"),
        ("Weekly heart rate summary", "weekly"),
        
        # Anomaly
        ("Show me outlier days for heart rate", "anomaly"),
        ("Unusual sleep nights", "anomaly"),
        ("Days with extreme step counts", "anomaly"),
    ]
    
    for q, expected_pattern in test_queries:
        print(f"\n{'─'*70}")
        print(f"Query: {q}")
        print(f"Expected pattern: {expected_pattern}")
        
        detected = detect_query_pattern(q)
        print(f"Detected pattern: {detected}")
        
        date = parse_date(q)
        sql, method = generate_sql(q, date)
        print(f"Method: {method}")
        
        if sql:
            preview = ' '.join(sql.split())[:150]
            print(f"SQL: {preview}...")
            result = execute_sql(sql, user_query=q, target_date=date)
            result_preview = result[:300].replace('\n', '\n      ')
            print(f"Result:\n      {result_preview}")

"""
- Less strict date validation 
- Better handling of mixed-date contexts
- Filter low-relevance journal entries before sending to LLM
"""

import re
from datetime import datetime

from config import (
    GEMINI_TEMPERATURE_INSIGHTS,
    DATABASE_START_DATE,
    DATABASE_END_DATE,
    DEBUG_MODE,
)
from gemini_client import call_gemini, is_gemini_available

def generate_insight(
    user_query: str,
    sql_data: str = None,
    journal_context: str = None,
    date: str = None,
    strategy: str = "both"
) -> str:
    """Generate intelligent insight by synthesizing data + context."""
    
    if not is_gemini_available():
        return _fallback_response(user_query, sql_data, journal_context, date)
    
    prompt = _build_prompt(
        user_query=user_query,
        sql_data=sql_data,
        journal_context=journal_context,
        date=date,
        strategy=strategy,
    )
    
    if DEBUG_MODE:
        print(f"[LLM] Generating insight")
    
    response = call_gemini(prompt, temperature=GEMINI_TEMPERATURE_INSIGHTS)
    
    if not response:
        return _fallback_response(user_query, sql_data, journal_context, date)
    
    if _has_problematic_dates(response):
        if DEBUG_MODE:
            print(f"[LLM] Response contains problematic dates, using fallback")
        return _fallback_response(user_query, sql_data, journal_context, date)
    
    return response

def _build_prompt(user_query, sql_data, journal_context, date, strategy):
    """Build context-aware prompt for Gemini."""
    query_type = _detect_query_type(user_query, sql_data or "")
    current_date = datetime.now().strftime("%Y-%m-%d")
    constraints = f"""
CONTEXT:
- Today's date: {current_date}
- Imported biometric data covers: {DATABASE_START_DATE} to {DATABASE_END_DATE}
- User can add new journal entries anytime (current date)
- Be honest about data availability - if data isn't there, say so

RULES:
- For imported biometrics (HR, sleep, steps): only reference dates in 2016 Apr-May
- For user journal entries: any date is valid (they're recent additions)
- NEVER fabricate data - if no data shown, say "no data available"
- Be CONCISE - 3-5 sentences max
"""
    sections = ["You are AURA, a health analytics assistant."]
    sections.append("Analyze the data provided and give actionable insights.")
    sections.append(constraints)
    sections.append(f"\nUSER QUERY: {user_query}")
    
    if date:
        sections.append(f"DATE REFERENCED: {date}")
    
    if sql_data:
        if "Data not available" in sql_data or "No data found" in sql_data:
            sections.append(f"\nBIOMETRIC DATA STATUS: {sql_data}")
        else:
            sections.append(f"\nBIOMETRIC DATA:\n{sql_data}")
    
    if journal_context and journal_context.strip():
        sections.append(f"\nJOURNAL ENTRIES (semantically reranked - top entries first):\n{journal_context}")
    
    instructions = _get_type_instructions(query_type, strategy, sql_data)
    sections.append(f"\n{instructions}")
    
    sections.append("\nGenerate your response (no preamble, no headers, just the analysis):")
    
    return "\n".join(sections)

def _detect_query_type(user_query: str, sql_data: str = "") -> str:
    """Detect query type for tailored response."""
    q = user_query.lower()
    
    if any(p in q for p in ["how much", "how many", "amount", "quantity"]):
        return "quantity"
    
    if any(p in q for p in ["compare", "vs ", "versus", "difference"]):
        return "comparison"
    if any(p in q for p in ["trend", "pattern", "over time"]):
        return "trend"
    if any(p in q for p in ["correlate", "correlation", "when i", "days when"]):
        return "correlation"
    if any(p in q for p in ["by hour", "time of day", "hourly"]):
        return "hourly"
    if any(p in q for p in ["per week", "weekly", "by week"]):
        return "weekly"
    if any(p in q for p in ["outlier", "unusual", "anomaly", "extreme"]):
        return "anomaly"
    if any(p in q for p in ["why", "reason", "cause"]):
        return "causal"
    if any(p in q for p in ["average", "avg", "mean", "max", "min"]):
        return "aggregate"
    
    return "simple"

def _get_type_instructions(query_type: str, strategy: str, sql_data: str = "") -> str:
    """Return instructions tailored to query type."""
    
    if query_type == "quantity":
        return """
YOUR TASK (QUANTITY QUESTION):
1. Check if biometric data has the answer (likely not for things like food/protein)
2. Check journal entries for the specific information requested
3. Extract the EXACT value or amount mentioned in journal entries
4. If found in journal: state it directly (e.g., "Based on your journal, you had 65g of protein")
5. If NOT found: say "I don't have that information in your data"
6. ONLY mention journal entries that are DIRECTLY RELEVANT to the question
7. Keep response 2-3 sentences MAX
"""
    
    instructions = {
        "comparison": """
YOUR TASK (COMPARISON):
1. Identify key differences between the periods/dates
2. Quantify changes with percentages or absolute differences
3. Highlight which metric improved or worsened
4. Provide ONE clear takeaway
5. Keep response 3-5 sentences
""",
        
        "trend": """
YOUR TASK (TREND):
1. Describe overall direction (improving, declining, stable)
2. Identify peaks, dips, and turning points
3. Brief actionable recommendation
4. Keep response 3-5 sentences
""",
        
        "correlation": """
YOUR TASK (CORRELATION):
1. Describe patterns across metrics
2. Identify dates where metrics align
3. Use "appears related to" not "caused by"
4. Suggest what this might indicate
5. Keep response 3-4 sentences
""",
        
        "hourly": """
YOUR TASK (HOURLY):
1. Identify peak and trough hours
2. Describe daily rhythm pattern
3. One insight about daily routine
4. Keep response 3-4 sentences
""",
        
        "weekly": """
YOUR TASK (WEEKLY):
1. Identify best and worst weeks
2. Compare weeks to each other
3. Brief actionable insight
4. Keep response 3-5 sentences
""",
        
        "anomaly": """
YOUR TASK (ANOMALY):
1. List most significant outlier dates
2. Describe HOW MUCH they deviated
3. Speculate on causes (with caution)
4. Keep response 3-5 sentences
""",
        
        "causal": """
YOUR TASK (CAUSAL):
1. Interpret biometric data
2. Connect to journal entries
3. Suggest likely reason
4. Use "may have been" not "was caused by"
5. Keep response 3-4 sentences
""",
        
        "aggregate": """
YOUR TASK (AGGREGATE):
1. State the key statistic clearly
2. Provide context (high/low/normal)
3. Brief interpretation
4. Keep response 2-3 sentences
""",
        
        "simple": """
YOUR TASK:
1. Summarize the data clearly
2. Highlight notable values
3. If journal entries are RELEVANT, mention them
4. Ignore irrelevant journal entries (don't force connections)
5. Keep response 2-3 sentences
""",
    }
    
    return instructions.get(query_type, instructions["simple"])


def _has_problematic_dates(response: str) -> bool:
    """
    FIXED: Only flag clearly fabricated biometric data dates.
    Allow current dates and 2016 dates.
    """
    biometric_patterns = [
        r'\d+\s*bpm.{0,30}(2017|2018|2019|2020|2021|2022|2023)',
        r'\d+\s*steps.{0,30}(2017|2018|2019|2020|2021|2022|2023)',
        r'\d+\s*hours?.{0,30}(2017|2018|2019|2020|2021|2022|2023)',
    ]
    
    for pattern in biometric_patterns:
        if re.search(pattern, response.lower()):
            return True
    
    return False

def _fallback_response(user_query, sql_data, journal_context, date):

    parts = []
    query_lower = user_query.lower()
    
    filtered_journal = _filter_relevant_journal(journal_context, query_lower)
    
    if sql_data and ("Data not available" in sql_data or "No data found" in sql_data):
        if filtered_journal:
            parts.append("Based on your journal entries:")
            parts.append(filtered_journal)
        else:
            parts.append("I don't have specific data for that query.")
            parts.append("Try asking about heart rate, sleep, or activity on a specific date.")
        return "\n\n".join(parts)
    if date:
        parts.append(f"**Data for {date}:**")
    elif sql_data:
        parts.append("**Data:**")
    if sql_data and "No data" not in sql_data and "Error" not in sql_data:
        parts.append(f"\n{sql_data}")
    if filtered_journal:
        parts.append(f"\n**Most Relevant Journal Entry:**\n{filtered_journal}")
    if len(parts) == 0:
        return "I couldn't find relevant data. Try a specific date in April-May 2016."
    return "\n".join(parts)


def _filter_relevant_journal(journal_context: str, query: str) -> str:
    """
    Filter journal entries to keep only the most relevant ones.
    Returns only entries that have keyword overlap with the query.
    """
    if not journal_context:
        return ""
    
    entries = re.findall(r'\[(\d{4}-\d{2}-\d{2})\]\s*([^\[]+?)(?=\[|\Z)', journal_context, re.DOTALL)
    
    if not entries:
        return journal_context
    
    stopwords = {'what', 'was', 'my', 'is', 'the', 'a', 'an', 'on', 'in', 'at', 
                 'how', 'much', 'did', 'i', 'take', 'to', 'do', 'have', 'and', 
                 'or', 'today', 'yesterday', 'why', 'when', 'where'}
    
    query_words = set(query.lower().split()) - stopwords
    
    scored = []
    for date_str, content in entries:
        content_words = set(content.lower().split())
        overlap = len(query_words & content_words)
        scored.append((overlap, date_str, content.strip()))
    
    scored.sort(key=lambda x: x[0], reverse=True)    
    relevant = [(d, c) for s, d, c in scored if s > 0]
    
    if not relevant:
        if scored:
            _, d, c = scored[0]
            return f"[{d}] {c}"
        return ""
    
    result = []
    for d, c in relevant[:2]:
        result.append(f"[{d}] {c}")
    
    return "\n".join(result)


if __name__ == "__main__":
    print("Testing LLM Interpreter\n")
    print("Test: Protein query (no SQL data, relevant journal)")
    response = generate_insight(
        user_query="how much protein did i take today?",
        sql_data="Data not available",
        journal_context="""[2026-06-17] Had a whey protein shake of 65gm protein as breakfast.
[2016-04-30] Only got 4 hours. My eyes are burning, need coffee ASAP.
[2016-04-21] Feel totally drained. I think I woke up like five times.""",
        date=None,
        strategy="both"
    )
    print(response)
    
    print("Test: Heart rate query (has SQL data)")
    response = generate_insight(
        user_query="What was my heart rate on May 9?",
        sql_data="""Time                   Value
2016-05-09 14:00:00     118
2016-05-09 13:00:00     112""",
        journal_context="",
        date="2016-05-09",
        strategy="sql_only"
    )
    print(response)

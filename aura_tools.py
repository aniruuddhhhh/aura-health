print("Initializing AURA...")

from config import DEBUG_MODE
from query_router import route_query, RetrievalStrategy
from sql_engine import generate_sql, execute_sql, parse_date
from retriever import search_journals, search_journals_with_trace
from llm_interpreter import generate_insight
from gemini_client import is_gemini_available

def run_query(user_input: str, chat_history: list[dict] | None = None) -> str:
    """Main query processing pipeline."""
    try:
        if DEBUG_MODE:
            print(f"[AURA] Query: {user_input}")
        
        decision = route_query(user_input)
        
        if DEBUG_MODE:
            print(f"[AURA] Strategy: {decision.strategy.value} ({decision.confidence:.0%})")
            print(f"[AURA] Reasoning: {decision.reasoning}")
        
        date = parse_date(user_input)
        if DEBUG_MODE and date:
            print(f"[AURA] Date extracted: {date}")
        
        sql_data = None
        journal_context = None
        sql_method = None
        
        if decision.strategy in [RetrievalStrategy.SQL_ONLY, RetrievalStrategy.BOTH]:
            sql, sql_method = generate_sql(user_input, date)
            if sql:
                sql_data = execute_sql(sql, user_query=user_input, target_date=date)
                
                if DEBUG_MODE:
                    preview = sql_data[:150] if sql_data else "None"
                    print(f"[AURA] SQL result preview: {preview}")
        
        if decision.strategy in [RetrievalStrategy.VECTOR_ONLY, RetrievalStrategy.BOTH]:
            journal_context = search_journals(user_input, date)
            
            if DEBUG_MODE and journal_context:
                print(f"[AURA] Journal entries found: {journal_context[:100]}...")
        
        has_sql = sql_data and "Error" not in sql_data
        has_journal = journal_context and journal_context.strip()
        
        if not has_sql and not has_journal:
            return (
                "No relevant data found. Try asking about specific dates "
                "between April 12 and May 12, 2016, or ask about your journal entries."
            )
        
        insight = generate_insight(
            user_query=user_input,
            sql_data=sql_data if has_sql else None,
            journal_context=journal_context if has_journal else None,
            date=date,
            strategy=decision.strategy.value,
        )
        
        response = _format_response(
            insight=insight,
            sql_data=sql_data if has_sql else None,
            journal_context=journal_context if has_journal else None,
        )
        
        if DEBUG_MODE:
            print(f"[AURA] Response ready")
        
        return response
        
    except Exception as e:
        if DEBUG_MODE:
            print(f"[AURA] Error: {e}")
        return f"Error: {str(e)}"

def _format_response(
    insight: str,
    sql_data: str = None,
    journal_context: str = None,
) -> str:
    
    parts = []
    
    if insight:
        parts.append(insight)
    
    if sql_data:
        if "No data found" in sql_data or "have data on these nearby" in sql_data:
            pass
        else:
            parts.append(f"\n**Data**\n```\n{sql_data}\n```")
    
    if journal_context:
        parts.append(f"\n**Related entries**\n{journal_context}")
    
    return "\n".join(parts)

print("AURA ready")

if __name__ == "__main__":
    test_queries = [
        "What was my heart rate on May 9?",
        "Why was I stressed?",
    ]
    
    for q in test_queries:
        print(f"Query: {q}")
        result = run_query(q)
        print(result)

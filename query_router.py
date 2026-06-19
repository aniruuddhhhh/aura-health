"""
Decides which data sources to use based on the query:
  - SQL_ONLY:     Pure numerical query (ex: "What was my heart rate?")
  - VECTOR_ONLY:  Pure contextual query (ex: "What was I feeling?")
  - BOTH:         Analytical query requiring both (ex: "Why was my HR high?")
key part of RAG architecture for retrieving the RIGHT data.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional

from config import DEBUG_MODE


class RetrievalStrategy(Enum):
    """Possible retrieval strategies."""
    SQL_ONLY = "sql_only"          
    VECTOR_ONLY = "vector_only"    
    BOTH = "both"                  
    NEITHER = "neither"            


@dataclass
class RouteDecision:
    """Decision about how to handle a query."""
    strategy: RetrievalStrategy
    reasoning: str
    confidence: float

SQL_INDICATORS = [
    "heart rate", "hr", "bpm", "pulse",
    "sleep", "slept", "hours of sleep", "minutes asleep",
    "steps", "walked", "walking",
    "calories", "burn", "burned",
    "activity", "exercise",

    "how much", "how many", "how long",
    "average", "maximum", "minimum", "max", "min",
    "total", "sum",
    "compare", "comparison", "versus", "vs",
    "more than", "less than", "above", "below",
    "highest", "lowest", "biggest", "smallest",
    # Date-based
    "on april", "on may", "yesterday", "today", "this week",
]

VECTOR_INDICATORS = [
    # "Why" questions need context
    "why", "because", "reason", "cause", "caused",
    # Emotional/subjective
    "feel", "feeling", "felt", "emotion",
    "stressed", "anxious", "happy", "sad", "tired",
    "mood", "energy", "energetic",
    # Activity context
    "doing", "did", "what was i", "what happened",
    "experience", "experienced",
    # Journal-related
    "journal", "note", "wrote", "diary",
    "remember", "recall",
    # Subjective state
    "good", "bad", "great", "terrible",
    "stressful", "relaxing", "exhausting",
]

# Words suggesting we need BOTH (analysis questions)
ANALYTICAL_INDICATORS = [
    "why was my", "why did my", "what caused",
    "explain", "interpret", "analyze",
    "pattern", "trend", "correlation",
    "what affects", "what impacts",
    "advice", "recommend", "suggest",
    "should i", "what should",
]

def route_query(query: str) -> RouteDecision:
    """
    Analyze the query and decide retrieval strategy.
    Logic:
        1. If query has analytical indicators → BOTH
        2. If query has SQL indicators AND vector indicators → BOTH
        3. If query has only SQL indicators → SQL_ONLY
        4. If query has only vector indicators → VECTOR_ONLY
        5. Default → BOTH (safer to have more context)
    """
    query_lower = query.lower()
    
    sql_matches = [w for w in SQL_INDICATORS if w in query_lower]
    vector_matches = [w for w in VECTOR_INDICATORS if w in query_lower]
    analytical_matches = [w for w in ANALYTICAL_INDICATORS if w in query_lower]
    
    if DEBUG_MODE:
        print(f"[Router] SQL indicators found: {sql_matches[:3]}")
        print(f"[Router] Vector indicators found: {vector_matches[:3]}")
        print(f"[Router] Analytical indicators found: {analytical_matches[:3]}")
    
    if analytical_matches:
        return RouteDecision(
            strategy=RetrievalStrategy.BOTH,
            reasoning=f"Analytical query (matched: {analytical_matches[0]}) - needs SQL + Journal",
            confidence=0.95
        )
    
    if sql_matches and vector_matches:
        return RouteDecision(
            strategy=RetrievalStrategy.BOTH,
            reasoning=f"Mixed query (numerical + contextual) - needs both sources",
            confidence=0.90
        )
    
    if sql_matches and not vector_matches:
        return RouteDecision(
            strategy=RetrievalStrategy.SQL_ONLY,
            reasoning=f"Numerical query - SQL primary (matched: {sql_matches[0]})",
            confidence=0.85
        )
    
    if vector_matches and not sql_matches:
        return RouteDecision(
            strategy=RetrievalStrategy.VECTOR_ONLY,
            reasoning=f"Contextual query - Journal primary (matched: {vector_matches[0]})",
            confidence=0.80
        )
    
    # No clear indicators - default to BOTH (safer)
    return RouteDecision(
        strategy=RetrievalStrategy.BOTH,
        reasoning="Ambiguous query - using both sources for safety",
        confidence=0.60
    )

if __name__ == "__main__":
    print("Testing Query Router\n")
    
    test_queries = [
        # SQL-only 
        "What was my heart rate on April 19?",
        "How many steps did I take?",
        "Average sleep duration this month",
        
        # Vector-only
        "What was I feeling stressed about?",
        "Did I journal about my workout?",
        
        # BOTH
        "Why was my heart rate high on April 14?",
        "What caused my poor sleep?",
        "Analyze my stress patterns",
        
        # Mixed
        "Was I stressed when my heart rate was high?",
    ]
    
    for q in test_queries:
        decision = route_query(q)
        print(f"\nQuery: {q}")
        print(f"  → Strategy: {decision.strategy.value}")
        print(f"  → Reasoning: {decision.reasoning}")
        print(f"  → Confidence: {decision.confidence:.0%}")

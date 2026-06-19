"""
Generates semantic variations of queries to catch synonyms.
Example:
  Input:  "why was I stressed at work"
  Output: ["why was I stressed at work",
           "why was I anxious at work",
           "why was I tense at work"]
part of the DOUBLE RETRIEVAL pipeline.
"""

import re
from config import MAX_QUERY_EXPANSIONS

SYNONYMS = {
    # Emotions
    "stressed": ["anxious", "worried", "tense", "pressured", "overwhelmed"],
    "stress": ["anxiety", "worry", "tension", "pressure"],
    "happy": ["joyful", "great", "good", "positive", "cheerful"],
    "sad": ["down", "depressed", "unhappy", "low"],
    "tired": ["exhausted", "fatigued", "drained", "sleepy"],
    "energetic": ["active", "vigorous", "lively"],
    
    # Activities
    "sleep": ["rest", "slept", "sleeping"],
    "exercise": ["workout", "training", "gym", "running"],
    "run": ["jog", "running", "cardio"],
    "meeting": ["call", "discussion", "conference"],
    "work": ["job", "office", "deadline"],
    
    # Health metrics
    "high": ["elevated", "increased", "spike"],
    "low": ["decreased", "reduced", "dropped"],
    "fast": ["rapid", "quick"],
    "slow": ["sluggish", "reduced"],
}

def expand_query(query: str, max_expansions: int = MAX_QUERY_EXPANSIONS) -> list[str]:
    """
    Generate semantic variations of a query.
    Args:
        query: Original user query
        max_expansions: Maximum number of variations to generate
    Returns:
        List of query variations (always includes original).
    Example:
        >>> expand_query("stressed at work", max_expansions=3)
        ['stressed at work', 'anxious at work', 'tense at work']
    """
    expansions = [query]
    query_lower = query.lower()
    
    for word, syns in SYNONYMS.items():
        if word in query_lower:
            for syn in syns[:2]:
                new_query = re.sub(
                    r'\b' + word + r'\b',
                    syn,
                    query_lower,
                    count=1
                )
                if new_query != query_lower and new_query not in expansions:
                    expansions.append(new_query)
                
                if len(expansions) >= max_expansions:
                    return expansions
    
    return expansions

if __name__ == "__main__":
    print("Testing query expansion:\n")
    
    test_queries = [
        "why was I stressed at work",
        "I felt tired and sad",
        "high heart rate after exercise",
    ]
    
    for q in test_queries:
        print(f"Original: {q}")
        expansions = expand_query(q)
        for i, e in enumerate(expansions, 1):
            print(f"  {i}. {e}")
        print()

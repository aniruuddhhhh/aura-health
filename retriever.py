"""
UPDATES:
- Filters out entries with very low rerank scores
- Only returns truly relevant entries to avoid confusing the LLM
- Configurable relevance threshold
"""
import time

from config import (
    CURRENT_USER_ID, INITIAL_RETRIEVAL_K, RERANK_TOP_K, DEBUG_MODE
)
from embeddings import get_vector_db
from query_expansion import expand_query
from reranker import rerank_candidates, rerank_with_scores, RERANKER_AVAILABLE

RELEVANCE_THRESHOLD = -8.0

def retrieve_wide(query: str, k: int = INITIAL_RETRIEVAL_K, date: str = None) -> list:
    """Stage 1: Wide retrieval using bi-encoder + query expansion."""
    vector_db = get_vector_db()
    if vector_db is None:
        return []
    
    expanded_queries = expand_query(query)
    
    if DEBUG_MODE:
        print(f"[Retriever] Stage 1: Wide retrieval")
        print(f"[Retriever] Expanded into {len(expanded_queries)} query variations:")
        for i, q in enumerate(expanded_queries, 1):
            print(f"  {i}. {q}")
    
    all_candidates = []
    seen_content = set()
    
    for exp_query in expanded_queries:
        if date:
            date_parts = date.split('-')
            month_name = "april" if date_parts[1] == "04" else "may"
            day = int(date_parts[2])
            search_text = f"{month_name} {day} 2016 {exp_query}"
        else:
            search_text = exp_query
        try:
            results = vector_db.similarity_search(
                search_text,
                k=k,
                filter={"user_id": str(CURRENT_USER_ID)}
            )
            
            for r in results:
                key = r.page_content[:80]
                if key not in seen_content:
                    seen_content.add(key)
                    all_candidates.append(r)
        except Exception as e:
            if DEBUG_MODE:
                print(f"[Retriever] Error retrieving for '{exp_query}': {e}")
            continue
    
    if date:
        all_candidates = [
            r for r in all_candidates
            if r.metadata.get('timestamp', '')[:10] == date
        ]
    
    if DEBUG_MODE:
        print(f"[Retriever] 📚 Retrieved {len(all_candidates)} unique candidates")
    
    return all_candidates


def search_journals(query: str, date: str = None, 
                    relevance_threshold: float = RELEVANCE_THRESHOLD) -> str:
    """
    Search with double retrieval + reranking + relevance filtering.
    Filters out entries with rerank score below threshold
    to avoid sending irrelevant context to the LLM.
    """
    vector_db = get_vector_db()
    if vector_db is None:
        return ""
    
    try:
        candidates = retrieve_wide(
            query=query,
            k=INITIAL_RETRIEVAL_K,
            date=date
        )
        
        if not candidates:
            return ""
        
        if RERANKER_AVAILABLE:
            scored_results = rerank_with_scores(
                query=query,
                candidates=candidates,
                top_k=RERANK_TOP_K
            )
            
            relevant_results = [
                (doc, score) for doc, score in scored_results
                if score > relevance_threshold
            ]
            
            if DEBUG_MODE:
                print(f"[Retriever] Filtered: {len(scored_results)} -> {len(relevant_results)} relevant entries")
                if len(scored_results) > len(relevant_results):
                    rejected = [(doc.page_content[:50], score) 
                                for doc, score in scored_results 
                                if score <= relevance_threshold]
                    print(f"[Retriever] Rejected (low relevance):")
                    for content, score in rejected:
                        print(f"  - score={score:.2f} | {content}")
            
            if not relevant_results:
                if DEBUG_MODE:
                    print(f"[Retriever] No entries passed relevance threshold")
                return ""
            
            reranked = [doc for doc, _ in relevant_results]
        else:
            reranked = candidates[:RERANK_TOP_K]
        
        if not reranked:
            return ""
        
        entries = [
            f"[{r.metadata.get('timestamp', '')[:10]}] {r.page_content[:200]}"
            for r in reranked
        ]
        
        if DEBUG_MODE:
            print(f"[Retriever] Returned {len(reranked)} relevant entries")
        
        return "\n".join(entries)
        
    except Exception as e:
        if DEBUG_MODE:
            print(f"[Retriever] Error: {e}")
        return ""

def search_journals_with_trace(query: str, date: str = None) -> dict:
    """Same as search_journals but returns detailed execution trace."""
    trace = {
        "original_query": query,
        "date_filter": date,
        "expanded_queries": [],
        "wide_retrieval_count": 0,
        "rerank_enabled": RERANKER_AVAILABLE,
        "final_results": [],
        "timings_ms": {}
    }
    
    vector_db = get_vector_db()
    if vector_db is None:
        trace["error"] = "Vector DB not available"
        return trace
    
    start = time.time()
    expansions = expand_query(query)
    trace["expanded_queries"] = expansions
    trace["timings_ms"]["expansion"] = round((time.time() - start) * 1000, 1)
    
    start = time.time()
    candidates = retrieve_wide(query, k=INITIAL_RETRIEVAL_K, date=date)
    trace["wide_retrieval_count"] = len(candidates)
    trace["timings_ms"]["wide_retrieval"] = round((time.time() - start) * 1000, 1)
    
    start = time.time()
    if candidates:
        reranked_with_scores = rerank_with_scores(query, candidates, top_k=RERANK_TOP_K)
        
        relevant = [(d, s) for d, s in reranked_with_scores if s > RELEVANCE_THRESHOLD]
        
        trace["final_results"] = [
            {
                "content": doc.page_content[:150],
                "timestamp": doc.metadata.get('timestamp', '')[:10],
                "rerank_score": score,
                "passed_filter": score > RELEVANCE_THRESHOLD,
            }
            for doc, score in reranked_with_scores
        ]
        trace["relevant_count"] = len(relevant)
    trace["timings_ms"]["reranking"] = round((time.time() - start) * 1000, 1)
    
    trace["timings_ms"]["total"] = round(
        sum(trace["timings_ms"].values()), 1
    )
    
    return trace

if __name__ == "__main__":
    print("Testing relevance filtering")
    
    test_queries = [
        "how much protein did i take today",
        "why was I stressed",
        "heart rate spike",
    ]
    
    for q in test_queries:
        print(f"\nQuery: {q}")
        result = search_journals(q)
        print(f"Result:\n{result if result else '(no relevant results)'}")

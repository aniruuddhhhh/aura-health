"""
Used:
HuggingFace cross-encoder/ms-marco-MiniLM-L-6-v2
- 100% FREE (runs locally)
- No API key needed
- 80MB model size
- ~50-100ms reranking time
- Trained on MS MARCO dataset (Microsoft's QA dataset)
"""

import time
from sentence_transformers import CrossEncoder

from config import RERANKER_MODEL, RERANK_TOP_K, DEBUG_MODE

print(f" Loading cross-encoder reranker: {RERANKER_MODEL}")

try:
    _reranker = CrossEncoder(RERANKER_MODEL)
    RERANKER_AVAILABLE = True
    print(" Cross-encoder reranker loaded (100% free, no API)")
except Exception as e:
    print(f" Reranker unavailable: {e}")
    print("    Will fall back to bi-encoder ranking only.")
    _reranker = None
    RERANKER_AVAILABLE = False

def rerank_candidates(query: str, candidates: list, top_k: int = RERANK_TOP_K) -> list:
    """
    Rerank candidates using cross-encoder for higher precision.
    Args:
        query: The user's search query
        candidates: List of LangChain Document objects from initial retrieval
        top_k: How many top results to return after reranking
    Returns:
        List of top-k Document objects, reordered by relevance.
    How it works:
        1. For each (query, document) pair, cross-encoder computes a score
        2. Higher score = more relevant
        3. Sort by score, return top-k
    """
    if not candidates:
        return []
    if not RERANKER_AVAILABLE or _reranker is None:
        if DEBUG_MODE:
            print("[Reranker] Reranker unavailable, using bi-encoder order")
        return candidates[:top_k]
    
    if DEBUG_MODE:
        print(f"[Reranker] Reranking {len(candidates)} candidates → top-{top_k}")
    
    pairs = [(query, doc.page_content) for doc in candidates]
    
    try:
        start = time.time()
        scores = _reranker.predict(pairs)
        elapsed_ms = (time.time() - start) * 1000
        scored_candidates = list(zip(candidates, scores))
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        reranked = [doc for doc, score in scored_candidates[:top_k]]
        
        if DEBUG_MODE:
            print(f"[Reranker] ⚡ Took {elapsed_ms:.0f}ms")
            print(f"[Reranker] Top {top_k} scores:")
            for i, (doc, score) in enumerate(scored_candidates[:top_k]):
                preview = doc.page_content[:60].replace('\n', ' ')
                print(f"  {i+1}. score={score:.3f} | {preview}...")
        
        return reranked
    
    except Exception as e:
        print(f"[Reranker] ❌ Reranking failed: {e}")
        return candidates[:top_k]

def rerank_with_scores(query: str, candidates: list, top_k: int = RERANK_TOP_K) -> list[tuple]:
    """
    Same as rerank_candidates but returns (document, score) tuples.
    Useful for showing rerank scores in UI / debugging.
    Returns:
        List of (Document, float_score) tuples, sorted by score descending.
    """
    if not candidates or not RERANKER_AVAILABLE:
        return [(doc, 0.0) for doc in candidates[:top_k]]
    
    pairs = [(query, doc.page_content) for doc in candidates]
    
    try:
        scores = _reranker.predict(pairs)
        scored = list(zip(candidates, scores))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [(doc, float(score)) for doc, score in scored[:top_k]]
    except Exception:
        return [(doc, 0.0) for doc in candidates[:top_k]]

if __name__ == "__main__":
    print("Testing cross-encoder reranking...")
    
    class MockDoc:
        def __init__(self, content):
            self.page_content = content
            self.metadata = {}
    
    query = "Why was I stressed at work?"
    docs = [
        MockDoc("Had a relaxing weekend at home."),
        MockDoc("Stressful meeting with the boss today, lots of pressure."),
        MockDoc("Went to the gym for an hour."),
        MockDoc("Felt anxious about the deadline at work."),
        MockDoc("Had pizza for dinner."),
    ]
    
    print(f"\nQuery: {query}\n")
    print("Before reranking (random order):")
    for i, d in enumerate(docs, 1):
        print(f"  {i}. {d.page_content}")
    
    print("\nAfter reranking (by relevance):")
    reranked = rerank_with_scores(query, docs, top_k=3)
    for i, (doc, score) in enumerate(reranked, 1):
        print(f"  {i}. [score={score:.3f}] {doc.page_content}")
    
    print("\n Most relevant documents are now on top!")

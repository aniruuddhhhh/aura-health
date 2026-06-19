"""
Works with both Pinecone and ChromaDB.
When user adds entry: saved to BOTH structured (Supabase/SQLite) 
and vector (Pinecone/ChromaDB) stores simultaneously.
"""
from datetime import datetime
import uuid

from config import CURRENT_USER_ID, DEBUG_MODE
from embeddings import get_vector_db, get_storage_type, get_vector_count
from session_manager import (
    save_journal_entry as save_to_structured,
    get_journals,
    get_storage_type as get_session_storage_type,
)


def add_journal_entry(entry_text: str, phase: str = "") -> dict:
    """
    Adds a journal entry to both structured and vector storage.
    Returns dict with: success, structured_saved, vector_saved, etc.
    """
    result = {
        "success": False,
        "structured_saved": False,
        "vector_saved": False,
        "timestamp": None,
        "error": None,
        "vector_storage": get_storage_type(),
        "structured_storage": get_session_storage_type(),
    }
    
    if not entry_text or not entry_text.strip():
        result["error"] = "Empty entry"
        return result
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    result["timestamp"] = timestamp
    
    # Save to structured storage (Supabase/SQLite)
    try:
        save_to_structured(entry_text.strip(), phase)
        result["structured_saved"] = True
        if DEBUG_MODE:
            print(f"[Journal] Saved to {get_session_storage_type()}: {entry_text[:50]}...")
    except Exception as e:
        result["error"] = f"Structured save failed: {e}"
        return result
    
    # Add to vector storage (Pinecone/ChromaDB)
    try:
        vector_db = get_vector_db()
        if vector_db is None:
            result["error"] = "Vector DB not available"
            return result
        
        doc_id = f"user_entry_{uuid.uuid4().hex[:12]}"
    
        vector_db.add_texts(
            texts=[entry_text.strip()],
            metadatas=[{
                "user_id": str(CURRENT_USER_ID),
                "timestamp": timestamp,
                "phase": phase,
                "source": "user_added",
            }],
            ids=[doc_id]
        )
        
        result["vector_saved"] = True
        result["doc_id"] = doc_id
        
        if DEBUG_MODE:
            print(f"[Journal] Vectorized in {get_storage_type()}: {doc_id}")
            count = get_vector_count()
            print(f"[Journal] Total vectors: {count}")
        
    except Exception as e:
        result["error"] = f"Vector save failed: {e}"
        if DEBUG_MODE:
            print(f"[Journal] Vector save error: {e}")
    
    result["success"] = result["structured_saved"]
    return result

def get_recent_journals(limit: int = 20) -> list:
    """Get recent journal entries"""
    journals = get_journals()
    return journals[:limit]

def get_journal_stats() -> dict:
    """Get statistics about stored journals"""
    journals = get_journals()
    return {
        "total_structured_entries": len(journals),
        "total_vector_entries": get_vector_count(),
        "vector_storage": get_storage_type(),
        "structured_storage": get_session_storage_type(),
    }

def search_user_added_journals(query: str, k: int = 5) -> list:
    """Search through user-added entries only."""
    try:
        vector_db = get_vector_db()
        if vector_db is None:
            return []
        
        results = vector_db.similarity_search(
            query,
            k=k,
            filter={"source": "user_added"}
        )
        
        return [
            {
                "content": r.page_content,
                "timestamp": r.metadata.get("timestamp", ""),
                "phase": r.metadata.get("phase", ""),
            }
            for r in results
        ]
    except Exception as e:
        if DEBUG_MODE:
            print(f"[Journal] Search error: {e}")
        return []

if __name__ == "__main__":
    print("Journal Manager Test")
    
    stats = get_journal_stats()
    print(f"\nStorage Status:")
    print(f"  Vector: {stats['vector_storage']}")
    print(f"  Structured: {stats['structured_storage']}")
    print(f"  Vector entries: {stats['total_vector_entries']}")
    print(f"  Structured entries: {stats['total_structured_entries']}")
    
    # Test add
    print(f"\n Adding test entry...")
    result = add_journal_entry(
        "Testing the persistent storage system today",
        "Morning"
    )
    print(f"Success: {result['success']}")
    print(f"Vector saved: {result['vector_saved']}")
    print(f"Structured saved: {result['structured_saved']}")

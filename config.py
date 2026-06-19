"""
config.py - Central configuration for AURA (Persistent Cloud Version)

FIX: Accepts multiple variable name conventions for flexibility.
"""
import os

# Load .env FIRST
try:
    from dotenv import load_dotenv
    load_dotenv()
    if not os.getenv("GEMINI_API_KEY"):
        load_dotenv("../.env")
except ImportError:
    print("WARNING: python-dotenv not installed. Run: pip install python-dotenv")


# User 
CURRENT_USER_ID = 2026352035

# Local SQLite 
SQL_DB_PATH = "aura_health.db"

# PINECONE
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "aura-journals")
PINECONE_DIMENSION = 384
PINECONE_METRIC = "cosine"
PINECONE_CLOUD = "aws"
PINECONE_REGION = "us-east-1"

# SUPABASE
SUPABASE_URL = os.getenv("SUPABASE_URL")

SUPABASE_KEY = (
    os.getenv("SUPABASE_KEY") or 
    os.getenv("SUPABASE_API_KEY") or    
    os.getenv("SUPABASE_ANON_KEY") or 
    os.getenv("SUPABASE_PUBLIC_KEY")
)

# LLM 
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_TEMPERATURE = 0
GEMINI_TEMPERATURE_INSIGHTS = 0.3

# Embeddings
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

# RAG Pipeline
INITIAL_RETRIEVAL_K = 20
RERANK_TOP_K = 3
MAX_QUERY_EXPANSIONS = 3

# Database Date Range 
DATABASE_START_DATE = "2016-04-12"
DATABASE_END_DATE = "2016-05-12"

# Storage Mode Detection 
USE_PINECONE = bool(PINECONE_API_KEY)
USE_SUPABASE = bool(SUPABASE_URL and SUPABASE_KEY)

# Debug 
import sys
DEBUG_MODE = not any('streamlit' in arg.lower() for arg in sys.argv)


# Show config status 
if DEBUG_MODE:
    print(f"\n[Config] Storage Configuration:")
    
    if GEMINI_API_KEY:
        masked = GEMINI_API_KEY[:6] + "..." + GEMINI_API_KEY[-4:]
        print(f"[Config]   GEMINI:   ENABLED ({masked})")
    else:
        print(f"[Config]   GEMINI:   NOT SET")
    
    if USE_PINECONE:
        masked = PINECONE_API_KEY[:6] + "..." + PINECONE_API_KEY[-4:]
        print(f"[Config]   PINECONE: ENABLED ({masked})")
        print(f"[Config]             Index: {PINECONE_INDEX_NAME}")
    else:
        print(f"[Config]   PINECONE: DISABLED (fallback to ChromaDB)")
    
    if USE_SUPABASE:
        masked = SUPABASE_KEY[:6] + "..." + SUPABASE_KEY[-4:]
        print(f"[Config]   SUPABASE: ENABLED")
        print(f"[Config]             URL: {SUPABASE_URL[:40]}...")
        print(f"[Config]             KEY: {masked}")
    else:
        if SUPABASE_URL and not SUPABASE_KEY:
            print(f"[Config]   SUPABASE: DISABLED (URL set, but KEY missing)")
            print(f"[Config]             Looked for: SUPABASE_KEY, SUPABASE_API_KEY,")
            print(f"[Config]                         SUPABASE_ANON_KEY, SUPABASE_PUBLIC_KEY")
        elif SUPABASE_KEY and not SUPABASE_URL:
            print(f"[Config]   SUPABASE: DISABLED (KEY set, but URL missing)")
        else:
            print(f"[Config]   SUPABASE: DISABLED (no credentials)")


if __name__ == "__main__":
    print("Config Self-Test")
    
    print(f"\nUser ID: {CURRENT_USER_ID}")
    print(f"Pinecone enabled: {USE_PINECONE}")
    print(f"Supabase enabled: {USE_SUPABASE}")
    
    if not (USE_PINECONE and USE_SUPABASE):
        print("\nIf keys aren't loading, run:")
        print("  python diagnose_env.py")
"""
If PINECONE_API_KEY set → use Pinecone (persistent)
Otherwise → use ChromaDB (local)
"""

from sentence_transformers import SentenceTransformer

from config import (
    EMBED_MODEL,
    USE_PINECONE,
    PINECONE_API_KEY,
    PINECONE_INDEX_NAME,
    PINECONE_DIMENSION,
    PINECONE_METRIC,
    PINECONE_CLOUD,
    PINECONE_REGION,
    DEBUG_MODE,
)

# Vector DB instance (Pinecone/Chroma)
_vector_db = None
_embeddings = None
_storage_type = None


class DirectEmbeddings:
    """Wrapper around SentenceTransformer for LangChain compatibility."""
    
    def __init__(self, model_name):
        print(f" Loading embedding model: {model_name}")
        self.model = SentenceTransformer(model_name)
        print(" Embedding model loaded")
    
    def embed_documents(self, texts):
        return self.model.encode(texts).tolist()
    
    def embed_query(self, text):
        return self.model.encode([text])[0].tolist()


def _setup_pinecone():
    """Initialize Pinecone vector store."""
    global _vector_db, _embeddings, _storage_type
    
    try:
        from pinecone import Pinecone, ServerlessSpec
        from langchain_pinecone import PineconeVectorStore
        
        print(" Connecting to Pinecone...")
        
        pc = Pinecone(api_key=PINECONE_API_KEY)
        
        # Check if index exists, create if not
        existing_indexes = [idx.name for idx in pc.list_indexes()]
        
        if PINECONE_INDEX_NAME not in existing_indexes:
            print(f" Creating Pinecone index: {PINECONE_INDEX_NAME}")
            pc.create_index(
                name=PINECONE_INDEX_NAME,
                dimension=PINECONE_DIMENSION,
                metric=PINECONE_METRIC,
                spec=ServerlessSpec(
                    cloud=PINECONE_CLOUD,
                    region=PINECONE_REGION,
                )
            )
            print(f" Index created: {PINECONE_INDEX_NAME}")
        
        # Get index
        index = pc.Index(PINECONE_INDEX_NAME)
        
        # Create embeddings
        _embeddings = DirectEmbeddings(EMBED_MODEL)
        
        # Create vector store using LangChain wrapper
        _vector_db = PineconeVectorStore(
            index=index,
            embedding=_embeddings,
            text_key="text",
        )
        
        _storage_type = "pinecone"
        
        # Get current count
        stats = index.describe_index_stats()
        total = stats.get('total_vector_count', 0)
        print(f" Pinecone connected. Total vectors: {total}")
        
        return True
        
    except Exception as e:
        print(f"  Pinecone setup failed: {e}")
        print(" Falling back to ChromaDB...")
        return False


def _setup_chromadb():
    """Fallback: Initialize ChromaDB (local, ephemeral)."""
    global _vector_db, _embeddings, _storage_type
    
    try:
        from langchain_chroma import Chroma
        
        VECTOR_DB_DIR = "./aura_vector_db_hf"
        
        _embeddings = DirectEmbeddings(EMBED_MODEL)
        _vector_db = Chroma(
            persist_directory=VECTOR_DB_DIR,
            embedding_function=_embeddings,
        )
        _storage_type = "chromadb"
        
        print(f" ChromaDB loaded from {VECTOR_DB_DIR}")
        return True
        
    except Exception as e:
        print(f" ChromaDB setup failed: {e}")
        return False


def initialize_storage():
    """Initialize storage - try Pinecone first, fall back to ChromaDB."""
    global _storage_type
    
    if USE_PINECONE:
        if _setup_pinecone():
            return True
    
    # Fallback to local ChromaDB
    return _setup_chromadb()


# Initialize on import
initialize_storage()


def get_vector_db():
    """Get the active vector DB (Pinecone or ChromaDB)."""
    return _vector_db


def get_storage_type():
    """Return 'pinecone' or 'chromadb' for UI display."""
    return _storage_type or "unknown"


def get_vector_count() -> int:
    """Get total number of vectors stored."""
    if _vector_db is None:
        return 0
    
    try:
        if _storage_type == "pinecone":
            # Pinecone way
            from pinecone import Pinecone
            pc = Pinecone(api_key=PINECONE_API_KEY)
            index = pc.Index(PINECONE_INDEX_NAME)
            stats = index.describe_index_stats()
            return stats.get('total_vector_count', 0)
        elif _storage_type == "chromadb":
            return _vector_db._collection.count()
    except Exception as e:
        if DEBUG_MODE:
            print(f"[Embeddings] Count error: {e}")
        return 0
    
    return 0


if __name__ == "__main__":
    print(f"\nStorage type: {get_storage_type()}")
    print(f"Total vectors: {get_vector_count()}")
    
    # Test search
    if _vector_db:
        print("\nTesting search...")
        try:
            results = _vector_db.similarity_search("stressed work", k=2)
            for r in results:
                print(f"  - {r.page_content[:80]}")
        except Exception as e:
            print(f"Search failed: {e}")

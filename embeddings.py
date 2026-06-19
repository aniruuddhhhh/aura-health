"""
embeddings.py - Vector Database (Pinecone with optional ChromaDB fallback)

Production: Uses Pinecone (cloud, persistent)
Local dev: Falls back to ChromaDB if Pinecone unavailable
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

_vector_db = None
_embeddings = None
_storage_type = None


class DirectEmbeddings:
    """Wrapper around SentenceTransformer for LangChain compatibility."""
    
    def __init__(self, model_name):
        print(f"Loading embedding model: {model_name}")
        self.model = SentenceTransformer(model_name)
        print("Embedding model loaded")
    
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
        
        print("Connecting to Pinecone...")
        
        pc = Pinecone(api_key=PINECONE_API_KEY)
        
        existing_indexes = [idx.name for idx in pc.list_indexes()]
        
        if PINECONE_INDEX_NAME not in existing_indexes:
            print(f"Creating Pinecone index: {PINECONE_INDEX_NAME}")
            pc.create_index(
                name=PINECONE_INDEX_NAME,
                dimension=PINECONE_DIMENSION,
                metric=PINECONE_METRIC,
                spec=ServerlessSpec(
                    cloud=PINECONE_CLOUD,
                    region=PINECONE_REGION,
                )
            )
            print(f"Index created: {PINECONE_INDEX_NAME}")
        
        index = pc.Index(PINECONE_INDEX_NAME)
        _embeddings = DirectEmbeddings(EMBED_MODEL)
        
        _vector_db = PineconeVectorStore(
            index=index,
            embedding=_embeddings,
            text_key="text",
        )
        
        _storage_type = "pinecone"
        
        stats = index.describe_index_stats()
        total = stats.get('total_vector_count', 0)
        print(f"Pinecone connected. Total vectors: {total}")
        
        return True
        
    except Exception as e:
        print(f"WARNING: Pinecone setup failed: {e}")
        return False


def _setup_chromadb():
    """Fallback: ChromaDB (only if installed)."""
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
        
        print(f"ChromaDB loaded from {VECTOR_DB_DIR}")
        return True
        
    except ImportError:
        print("WARNING: ChromaDB not installed. Vector storage unavailable.")
        return False
    except Exception as e:
        print(f"WARNING: ChromaDB setup failed: {e}")
        return False


def initialize_storage():
    """Initialize storage - try Pinecone first, fall back to ChromaDB."""
    if USE_PINECONE:
        if _setup_pinecone():
            return True
    
    return _setup_chromadb()


initialize_storage()


def get_vector_db():
    return _vector_db


def get_storage_type():
    return _storage_type or "none"


def get_vector_count() -> int:
    if _vector_db is None:
        return 0
    
    try:
        if _storage_type == "pinecone":
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

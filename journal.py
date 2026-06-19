"""
Loads CSV journal entries into vector storage (Pinecone/ChromaDB).
"""

import os
import time
import pandas as pd

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import CURRENT_USER_ID, EMBED_MODEL, USE_PINECONE
from embeddings import get_vector_db, get_storage_type, get_vector_count

JOURNAL_FILE = "data/filtered_AURA_Realistic_Journals (1).csv"

def build_vector_memory():
    """Load journal CSV into the active vector store."""
    print(f" AURA: Loading journals into {get_storage_type()} ")

    if not os.path.exists(JOURNAL_FILE):
        print(f"ERROR: Journal file not found: {JOURNAL_FILE}")
        return
    
    # Load CSV
    print(f"Loading {JOURNAL_FILE}...")
    df = pd.read_csv(JOURNAL_FILE)
    print(f"  Columns: {list(df.columns)}")
    print(f"  Total rows: {len(df)}")
    
    # Filter for current user
    documents = [
        Document(
            page_content=str(row["Entry"]),
            metadata={
                "user_id": str(row["Id"]).strip(),
                "timestamp": str(row["Timestamp"]),
                "phase": str(row.get("Phase", "")),
                "source": "csv_import",
            }
        )
        for _, row in df.iterrows()
        if str(row["Id"]).strip() == str(CURRENT_USER_ID)
    ]
    
    print(f"Filtered {len(documents)} entries for User {CURRENT_USER_ID}")
    
    if len(documents) == 0:
        print(f"WARNING: No entries found for user {CURRENT_USER_ID}")
        print("Check user ID in config.py")
        return
    
    # Chunk if needed
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    split_docs = splitter.split_documents(documents)
    print(f"Created {len(split_docs)} chunks")
    
    # Get vector store
    vector_db = get_vector_db()
    if vector_db is None:
        print("ERROR: Vector DB not available!")
        return
    
    current_count = get_vector_count()
    print(f"\nCurrent vectors in storage: {current_count}")
    
    # Check if already populated
    if current_count >= len(split_docs):
        response = input(f"\nStorage already has {current_count} vectors. Re-upload? (y/n): ")
        if response.lower() != 'y':
            print("Skipping upload.")
            return
    
    # Upload to vector store
    print(f"\nUploading {len(split_docs)} documents...")
    start = time.time()
    
    try:
        # Generate IDs
        ids = [f"csv_{i}_{CURRENT_USER_ID}" for i in range(len(split_docs))]
        
        # Batch upload
        batch_size = 50 if USE_PINECONE else 100
        
        for i in range(0, len(split_docs), batch_size):
            batch = split_docs[i:i+batch_size]
            batch_ids = ids[i:i+batch_size]
            
            vector_db.add_documents(
                documents=batch,
                ids=batch_ids,
            )
            print(f"  Uploaded batch {i//batch_size + 1}/{(len(split_docs)-1)//batch_size + 1}")
        
        elapsed = time.time() - start
        print(f"\n Upload complete! Time: {elapsed:.1f}s")
        new_count = get_vector_count()
        print(f"Total vectors now: {new_count}")
        
        # search
        print("\nTesting search...")
        results = vector_db.similarity_search("stressed work meeting", k=2)
        for i, r in enumerate(results[:2], 1):
            preview = r.page_content[:80].replace('\n', ' ')
            print(f"  {i}. '{preview}...'")
        
    except Exception as e:
        print(f"\n Upload failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    build_vector_memory()

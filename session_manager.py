"""
If SUPABASE_URL/KEY set → use Supabase (persistent cloud)
Otherwise →SQLite (local)
Same API for both - rest of code doesn't change.
"""

import sqlite3
from datetime import datetime
from typing import Optional

from config import USE_SUPABASE, SUPABASE_URL, SUPABASE_KEY, DEBUG_MODE

SESSION_DB = "aura_session.db"
_supabase_client = None
_storage_type = None

def _setup_supabase():
    """Initialize Supabase client and ensure tables exist."""
    global _supabase_client, _storage_type
    try:
        from supabase import create_client
        
        print(" Connecting to Supabase...")
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        try:
            _supabase_client.table("chat_history").select("id").limit(1).execute()
            _storage_type = "supabase"
            print(" Supabase connected. Tables verified.")
            return True
        except Exception as e:
            print(f" Supabase tables not found: {e}")
            print(" Please run the SQL setup from SUPABASE_SETUP.md")
            return False
            
    except Exception as e:
        print(f" Supabase setup failed: {e}")
        return False


def _setup_sqlite():
    """Fallback: Use local SQLite."""
    global _storage_type
    
    conn = sqlite3.connect(SESSION_DB, check_same_thread=False)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL
        );
        
        CREATE TABLE IF NOT EXISTS journals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            entry TEXT NOT NULL,
            phase TEXT DEFAULT ''
        );
        
        CREATE TABLE IF NOT EXISTS preferences (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()
    
    _storage_type = "sqlite"
    print(f" SQLite ready: {SESSION_DB}")
    return True


def initialize():
    """Try Supabase first, fall back to SQLite."""
    if USE_SUPABASE:
        if _setup_supabase():
            return
    _setup_sqlite()

initialize()


def get_storage_type():
    """Return 'supabase' or 'sqlite' for UI display."""
    return _storage_type or "unknown"

# CHAT HISTORY

def save_message(role: str, content: str) -> None:
    """Save a chat message."""
    timestamp = datetime.now().isoformat()
    
    if _storage_type == "supabase":
        try:
            _supabase_client.table("chat_history").insert({
                "role": role,
                "content": content,
                "timestamp": timestamp,
            }).execute()
        except Exception as e:
            if DEBUG_MODE:
                print(f"[Session] Supabase save error: {e}")
    else:
        conn = sqlite3.connect(SESSION_DB, check_same_thread=False)
        conn.execute(
            "INSERT INTO chat_history (role, content, timestamp) VALUES (?,?,?)",
            (role, content, timestamp),
        )
        conn.commit()
        conn.close()

def load_chat_history(limit: int = 50) -> list[dict]:
    """Load recent chat history."""
    if _storage_type == "supabase":
        try:
            response = (_supabase_client.table("chat_history")
                       .select("role,content,timestamp")
                       .order("id", desc=True)
                       .limit(limit)
                       .execute())
            return list(reversed(response.data))
        except Exception as e:
            if DEBUG_MODE:
                print(f"[Session] Supabase load error: {e}")
            return []
    else:
        # SQLite
        conn = sqlite3.connect(SESSION_DB, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT role, content, timestamp FROM chat_history ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        conn.close()
        return [
            {"role": r["role"], "content": r["content"], "timestamp": r["timestamp"]}
            for r in reversed(rows)
        ]

def clear_chat_history() -> None:
    """Clear all chat history."""
    if _storage_type == "supabase":
        try:
            _supabase_client.table("chat_history").delete().neq("id", 0).execute()
        except Exception as e:
            if DEBUG_MODE:
                print(f"[Session] Supabase clear error: {e}")
    else:
        conn = sqlite3.connect(SESSION_DB, check_same_thread=False)
        conn.execute("DELETE FROM chat_history")
        conn.commit()
        conn.close()

# JOURNALS

def save_journal_entry(entry: str, phase: str = "") -> None:
    """Save a journal entry to structured storage."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if _storage_type == "supabase":
        try:
            _supabase_client.table("journals").insert({
                "timestamp": timestamp,
                "entry": entry,
                "phase": phase,
            }).execute()
        except Exception as e:
            if DEBUG_MODE:
                print(f"[Session] Supabase save error: {e}")
    else:
        conn = sqlite3.connect(SESSION_DB, check_same_thread=False)
        conn.execute(
            "INSERT INTO journals (timestamp, entry, phase) VALUES (?,?,?)",
            (timestamp, entry, phase),
        )
        conn.commit()
        conn.close()

def get_journals() -> list[dict]:
    """Get all journal entries."""
    if _storage_type == "supabase":
        try:
            response = (_supabase_client.table("journals")
                       .select("timestamp,entry,phase")
                       .order("timestamp", desc=True)
                       .execute())
            return response.data
        except Exception as e:
            if DEBUG_MODE:
                print(f"[Session] Supabase load error: {e}")
            return []
    else:
        conn = sqlite3.connect(SESSION_DB, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT timestamp, entry, phase FROM journals ORDER BY timestamp DESC"
        ).fetchall()
        conn.close()
        return [
            {"timestamp": r["timestamp"], "entry": r["entry"], "phase": r["phase"]}
            for r in rows
        ]

# PREFERENCES

def get_preference(key: str, default: Optional[str] = None) -> Optional[str]:
    """Get a user preference."""
    if _storage_type == "supabase":
        try:
            response = (_supabase_client.table("preferences")
                       .select("value")
                       .eq("key", key)
                       .execute())
            if response.data:
                return response.data[0]["value"]
            return default
        except:
            return default
    else:
        conn = sqlite3.connect(SESSION_DB, check_same_thread=False)
        row = conn.execute(
            "SELECT value FROM preferences WHERE key = ?", (key,)
        ).fetchone()
        conn.close()
        return row[0] if row else default

def set_preference(key: str, value: str) -> None:
    """Set a user preference."""
    if _storage_type == "supabase":
        try:
            _supabase_client.table("preferences").upsert({
                "key": key,
                "value": value,
            }).execute()
        except Exception as e:
            if DEBUG_MODE:
                print(f"[Session] Supabase pref error: {e}")
    else:
        conn = sqlite3.connect(SESSION_DB, check_same_thread=False)
        conn.execute(
            "INSERT OR REPLACE INTO preferences (key, value) VALUES (?,?)",
            (key, value),
        )
        conn.commit()
        conn.close()


if __name__ == "__main__":
    print(f"\nStorage type: {get_storage_type()}")
    print(f"\nTesting save/load...")
    
    save_message("user", "test message")
    save_message("assistant", "test response")
    
    history = load_chat_history(5)
    print(f"\nLoaded {len(history)} messages:")
    for m in history:
        print(f"  [{m['role']}] {m['content'][:50]}")

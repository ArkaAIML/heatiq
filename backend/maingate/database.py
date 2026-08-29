import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import hashlib
import secrets

DB_PATH = Path(__file__).parent / "keys.db"

def init_db():
    """Initialize the SQLite database for API Keys."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                key_id TEXT PRIMARY KEY,
                hashed_key TEXT NOT NULL,
                label TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                revoked_at TEXT
            )
        """)
        conn.commit()

def hash_key(api_key: str) -> str:
    """Creates a SHA-256 hash of the API key for secure storage."""
    return hashlib.sha256(api_key.encode()).hexdigest()

def generate_key(label: str = "Main Gate API Key") -> tuple[str, str]:
    """Generates a secure API key, stores its hash, and returns (key_id, raw_key)."""
    raw_key = f"hk_{secrets.token_urlsafe(32)}"
    key_id = f"kid_{secrets.token_hex(8)}"
    hashed = hash_key(raw_key)
    created_at = datetime.now(timezone.utc).isoformat()
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO api_keys (key_id, hashed_key, label, status, created_at) VALUES (?, ?, ?, ?, ?)",
            (key_id, hashed, label, "active", created_at)
        )
        conn.commit()
        
    return key_id, raw_key

def revoke_key(key_id: str) -> bool:
    """Marks an API key as revoked."""
    revoked_at = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE api_keys SET status = ?, revoked_at = ? WHERE key_id = ?",
            ("revoked", revoked_at, key_id)
        )
        conn.commit()
        return cursor.rowcount > 0

def is_key_valid(raw_key: str) -> bool:
    """Checks if a provided raw API key is valid and active."""
    hashed = hash_key(raw_key)
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM api_keys WHERE hashed_key = ?", (hashed,))
        row = cursor.fetchone()
        
        if row and row[0] == "active":
            return True
        return False

def list_keys() -> List[Dict[str, Any]]:
    """Returns metadata for all API keys (without raw keys)."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT key_id, label, status, created_at, revoked_at FROM api_keys ORDER BY created_at DESC")
        return [dict(row) for row in cursor.fetchall()]

# Ensure DB is initialized when module is loaded
init_db()

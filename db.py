import sqlite3
from pathlib import Path

DB_PATH = Path("lostandfound.db")

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS found_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  category TEXT NOT NULL,
  location_found TEXT NOT NULL,
  location_id TEXT,
  date_found TEXT NOT NULL,
  description TEXT NOT NULL,
  photo_filename TEXT,
  status TEXT NOT NULL DEFAULT 'pending',  -- pending | approved | claimed
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS claims (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  item_id INTEGER NOT NULL,
  student_name TEXT NOT NULL,
  email TEXT NOT NULL,
  message TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(item_id) REFERENCES found_items(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message TEXT NOT NULL,
    rating INTEGER NOT NULL DEFAULT 5,
    created_at TEXT NOT NULL
);
"""

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    conn = get_conn()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()

    

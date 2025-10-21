import sqlite3
from contextlib import closing

DB_PATH = "videos.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  source TEXT NOT NULL,      -- 's3' or 'youtube'
  s3_key TEXT,               -- object key if source=='s3'
  youtube_url TEXT,          -- url if source=='youtube'
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  views INTEGER DEFAULT 0,
  likes INTEGER DEFAULT 0
);
"""

def init_db():
    with closing(sqlite3.connect(DB_PATH)) as con:
        con.executescript(SCHEMA)
        con.commit()


def query(sql, params=()):
    with closing(sqlite3.connect(DB_PATH)) as con:
        cur = con.execute(sql, params)
        rows = cur.fetchall()
    return rows


def execute(sql, params=()):
    with closing(sqlite3.connect(DB_PATH)) as con:
        con.execute(sql, params)
        con.commit()

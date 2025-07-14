import sqlite3
from datetime import datetime

conn = sqlite3.connect('volunteer.db')
cursor = conn.cursor()

# tworzenie tabel
def init_db():
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            discord_id TEXT PRIMARY KEY,
            github_login TEXT NOT NULL,
            validated_at TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS commits (
            id TEXT PRIMARY KEY,
            github_login TEXT,
            committed_at TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_id TEXT,
            commit_id TEXT,
            hours REAL,
            logged_at TEXT
        )
    ''')
    conn.commit()

#   users  (login <-> github nazwa użytkownika)
    
def add_user(discord_id, login):
    """Dodaje lub aktualizuje użytkownika (po weryfikacji)."""
    cursor.execute(
        'INSERT OR REPLACE INTO users(discord_id, github_login, validated_at) VALUES (?,?,?)',
        (discord_id, login, datetime.now(datetime.UTC).isoformat())
    )
    conn.commit()
def get_user(discord_id):
    row = cursor.execute(
        'SELECT discord_id, github_login, validated_at FROM users WHERE discord_id=?',
        (discord_id,)
    ).fetchone()
    return dict(zip(['discord_id','github_login','validated_at'], row)) if row else None


def unlink_user(discord_id):
    """Usuwa powiązanie użytkownika."""
    cursor.execute(
        'DELETE FROM users WHERE discord_id=?',
        (discord_id,)
    )
    conn.commit()

#   commits

def add_commit(commit_id, login, date):
    """Zapisuje commit do tabeli (można pre‑fillować historycznie)."""
    cursor.execute(
        'INSERT OR REPLACE INTO commits(id, github_login, commited_at) VALUES (?,?,?)',
        (commit_id, login, date)
    )
    conn.commit()

def get_commits_for_user(login, since_iso):
    rows = cursor.execute(
        'SELECT id, commited_at FROM commits WHERE github_login=? AND committed_at>=? ORDER BY committed_at DESC',
        (login, since_iso)
    ).fetchall()
    return [{'id':id_, 'date':datetime} for id_, date in rows]

#   logi 
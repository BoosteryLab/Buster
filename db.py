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
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS oauth_states (
            state TEXT PRIMARY KEY,
            discord_id TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    ''')
    conn.commit()

#   users  (login <-> github nazwa użytkownika)
    
def add_user(discord_id, login):
    """Dodaje lub aktualizuje użytkownika (po weryfikacji)."""
    cursor.execute(
        'INSERT OR REPLACE INTO users(discord_id, github_login, validated_at) VALUES (?,?,?)',
        (discord_id, login, datetime.utcnow().isoformat())
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
        'INSERT OR REPLACE INTO commits(id, github_login, committed_at) VALUES (?,?,?)',
        (commit_id, login, date)
    )
    conn.commit()

def get_commits_for_user(login, since_iso):
    rows = cursor.execute(
        'SELECT id, committed_at FROM commits WHERE github_login=? AND committed_at>=? ORDER BY committed_at DESC',
        (login, since_iso)
    ).fetchall()
    return [{'id':id_, 'date':date} for id_, date in rows]

#   logi 
def log_hours(discord_id, commit_id, hours):
    cursor.execute(
        'INSERT INTO logs(discord_id, commit_id, hours, logged_at) VALUES(?,?,?,?)',
        (discord_id, commit_id, hours, datetime.utcnow().isoformat())
    )
    conn.commit()
def get_recent_logs(discord_id, limit=5):
    rows = cursor.execute(
        'SELECT commit_id, hours, logged_at FROM logs WHERE discord_id=? ORDER BY logged_at DESC LIMIT ?',
        (discord_id, limit)
    ).fetchall()
    return rows
def get_summary(discord_id):
    row = cursor.execute(
        'SELECT SUM(hours), COUNT(*) FROM logs WHERE discord_id=?',
        (discord_id,)
    ).fetchone()
    return {'total_hours': row[0] or 0, 'entries': row[1]}

# OAUTH

def save_state(state, discord_id):
    cursor.execute(
        'INSERT OR REPLACE INTO oauth_states(state, discord_id, created_at) VALUES (?,?,?)',
        (state, discord_id, datetime.utcnow().isoformat())
    )
    conn.commit()

def get_state(state):
    row = cursor.execute(
        'SELECT discord_id, created_at FROM oauth_states WHERE state=?',
        (state,)
    ).fetchone()
    return {'discord_id': row[0], 'created_at': row[1]} if row else None

def delete_state(state):
    cursor.execute(
        'DELETE FROM oauth_states WHERE state=?',
        (state,)
    )
    conn.commit()

# EXPORT

def export_logs_to_csv(discord_id, filename='export.csv'):
    import csv
    rows = cursor.execute(
        'SELECT commit_id, hours, logged_at FROM logs WHERE discord_id=? ORDER BY logged_at',
        (discord_id,)
    ).fetchall()
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['commit_id', 'hours', 'logged_at'])
        writer.writerows(rows)
    return filename
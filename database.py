import sqlite3
import os
import json

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "bot.db")

def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_cookies (
            user_id TEXT PRIMARY KEY,
            cookie TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tracking (
            asset_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            moderated INTEGER DEFAULT 0,
            notified INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

def get_user_cookie(user_id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT cookie FROM user_cookies WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row["cookie"]
    return None

def set_user_cookie(user_id: str, cookie: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO user_cookies (user_id, cookie) VALUES (?, ?)", (user_id, cookie))
    conn.commit()
    conn.close()

def delete_user_cookie(user_id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_cookies WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_all_tracked_assets():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT asset_id, user_id, moderated FROM tracking")
    rows = cursor.fetchall()
    conn.close()
    return [{"asset_id": row["asset_id"], "user_id": row["user_id"], "moderated": row["moderated"]} for row in rows]

def add_tracked_asset(asset_id: str, user_id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO tracking (asset_id, user_id, moderated) VALUES (?, ?, 0)", (asset_id, user_id))
    conn.commit()
    conn.close()

def remove_tracked_asset(asset_id: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tracking WHERE asset_id = ?", (asset_id,))
    conn.commit()
    conn.close()

def update_tracked_asset_moderated(asset_id: str, moderated: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE tracking SET moderated = ? WHERE asset_id = ?", (moderated, asset_id))
    conn.commit()
    conn.close()
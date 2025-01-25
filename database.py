# database.py
import sqlite3
from datetime import datetime

class Database:
    def __init__(self, db_name="henry_ai.db"):
        self.conn = sqlite3.connect(db_name)
        self.create_tables()

    def create_tables(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY,
                group_id INTEGER,
                user_id INTEGER,
                content TEXT,
                timestamp DATETIME,
                processed BOOLEAN DEFAULT 0
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS topics (
                id INTEGER PRIMARY KEY,
                topic TEXT,
                used_times INTEGER DEFAULT 0,
                last_used DATETIME
            )
        """)
        self.conn.commit()

    def add_message(self, group_id, user_id, content):
        self.conn.execute(
            "INSERT INTO messages (group_id, user_id, content, timestamp) VALUES (?, ?, ?, ?)",
            (group_id, user_id, content, datetime.now())
        )
        self.conn.commit()

    def get_offline_messages(self, group_id, last_online_time):
        cursor = self.conn.execute("""
            SELECT user_id, content, id 
            FROM messages 
            WHERE 
                group_id = ? 
                AND processed = 0 
                AND timestamp > ?
        """, (group_id, last_online_time))
        return cursor.fetchall()

    def mark_as_processed(self, msg_id):
        self.conn.execute("UPDATE messages SET processed = 1 WHERE id = ?", (msg_id,))
        self.conn.commit()
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
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER UNIQUE,
                group_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                processed INTEGER DEFAULT 0
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

    def add_message(self, message_id, group_id, user_id, content):
        self.conn.execute(
            "INSERT INTO messages (message_id, group_id, user_id, content, timestamp) VALUES (?, ?, ?, ?, ?)",
            (message_id, group_id, user_id, content, datetime.now())
        )
        self.conn.commit()
        print(f"[DB] Tin nhắn đã được lưu vào database - Group: {group_id}, User: {user_id}, Nội dung: {content}")

    def get_offline_messages(self, group_id, last_online_time):
        try:
            cursor = self.conn.execute("""
                SELECT user_id, content, message_id, timestamp 
                FROM messages 
                WHERE 
                    group_id = ? 
                    AND processed = 0 
                    AND timestamp > ?
            """, (group_id, last_online_time))

            messages = cursor.fetchall()

            print(f"[DB] Số tin nhắn offline lấy được từ DB cho Group {group_id}: {len(messages)}")

            if messages:
                for msg in messages:
                    print(f"[DB] Tin nhắn: ID={msg[2]}, User={msg[0]}, Nội dung={msg[1]}, Thời gian={msg[3]}")

            return messages

        except Exception as e:
            print(f"[ERROR] Lỗi trong get_offline_messages: {e}")
            return []


    def mark_as_processed(self, message_id):
        """Đánh dấu tin nhắn là đã xử lý bằng cách cập nhật processed = 1"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("UPDATE messages SET processed = 1 WHERE message_id = ?", (message_id,))
            self.conn.commit()

            # Kiểm tra lại xem dữ liệu đã thực sự cập nhật chưa
            cursor.execute("SELECT processed FROM messages WHERE message_id = ?", (message_id,))
            result = cursor.fetchone()

            if result:
                print(f"[DB] ✅ Xác nhận: Tin nhắn ID {message_id} đã cập nhật thành công (processed = {result[0]})")
            else:
                print(f"[ERROR] ❌ Tin nhắn ID {message_id} KHÔNG tồn tại trong database!")

        except Exception as e:
            print(f"[ERROR] ❌ Lỗi khi cập nhật processed = 1 cho tin nhắn {message_id}: {e}")


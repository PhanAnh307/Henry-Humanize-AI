# topic_generator.py
from groq import Groq
import random
from datetime import datetime, timedelta
import sqlite3

class TopicGenerator:
    def __init__(self, groq_client):
        self.client = groq_client
        self.conn = sqlite3.connect("henry_ai.db")
        self._create_table()

    def _create_table(self):
        """Tạo bảng lưu chủ đề đã gửi."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS sent_topics (
                id INTEGER PRIMARY KEY,
                topic TEXT,
                sent_date DATETIME
            )
        """)
        self.conn.commit()

    def generate_topic(self):
        """Sinh chủ đề mới bằng Groq/Llama3."""
        prompt = """
    You are a friendly and active member of a group chat. Write a casual and engaging message to spark conversation. 
    Focus on simple, everyday topics that don't require up-to-date information from the internet. 
    Examples:
    - Any good stuff to hold?
    - Guys, i need some advice
    - Im lost half of my fund so sad
    - Anyone tried cooking something new recently? Share your recipes!
    Keep the message short, fun, and conversational.
        """
        response = self.client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=50
        )
        return response.choices[0].message.content.strip()

    def is_topic_used(self, topic):
        """Kiểm tra chủ đề đã được gửi trong 7 ngày qua chưa."""
        query = """
        SELECT * FROM sent_topics 
        WHERE topic = ? AND sent_date > ?
        """
        last_week = datetime.now() - timedelta(days=7)
        cursor = self.conn.execute(query, (topic, last_week))
        return cursor.fetchone() is not None

    def save_topic(self, topic):
        """Lưu chủ đề vào database."""
        self.conn.execute(
            "INSERT INTO sent_topics (topic, sent_date) VALUES (?, ?)",
            (topic, datetime.now())
        )
        self.conn.commit()
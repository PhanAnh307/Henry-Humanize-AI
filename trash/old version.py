from telethon import TelegramClient, events
import os
import pickle
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from groq import Groq
import json
from datetime import datetime
import time
import sys

# --- CONFIGURATION ---
sys.stdout.reconfigure(encoding='utf-8')
API_ID = "24842750"           # Thay bằng API ID từ Telegram
API_HASH = "d1e89c4c6c6698d18fde9119cd6408c9"       # Thay bằng API Hash từ Telegram
SESSION_NAME = "henry"      # Tên session (file lưu trữ đăng nhập)
FAISS_INDEX_FILE = "faiss_index.bin"
FAISS_META_FILE = "faiss_meta.pkl"


#-----LOAD CONFIG-----
def load_channel_whitelist(file_path="channels.json"):
    try:
        with open(file_path, "r") as file:
            channels = json.load(file)
        return {channel["id"]: channel["name"] for channel in channels}
    except Exception as e:
        print(f"Không thể tải danh sách kênh: {e}")
        return {}

CHANNEL_WHITELIST = load_channel_whitelist()
# --- SETUP ---
api_key = "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"
client = Groq(api_key=api_key)
model = SentenceTransformer('all-MiniLM-L6-v2')  # Mô hình có 384 chiều

# Load or create FAISS index
def load_faiss_index(filename=FAISS_INDEX_FILE):
    if os.path.exists(filename):
        # print(f"Tìm thấy FAISS index tại {filename}, đang tải...")
        return faiss.read_index(filename)
    else:
        # print(f"Không tìm thấy FAISS index tại {filename}, tạo FAISS index mới.")
        return faiss.IndexFlatL2(384)  # FAISS index với 384 chiều vector
def save_faiss_index(index, filename=FAISS_INDEX_FILE):
    faiss.write_index(index, filename)
    # print(f"FAISS index đã được lưu tại {filename}.")

index = load_faiss_index()

# Load or create metadata
def load_faiss_metadata(filename=FAISS_META_FILE):
    try:
        with open(filename, "rb") as f:
            # print(f"Tìm thấy metadata tại {filename}, đang tải...")
            return pickle.load(f)
    except FileNotFoundError:
        # print(f"Không tìm thấy metadata tại {filename}, tạo metadata mới.")
        return []

def save_faiss_metadata(metadata, filename=FAISS_META_FILE):
    with open(filename, "wb") as f:
        pickle.dump(metadata, f)
    # print(f"Metadata đã được lưu tại {filename}.")

metadata = load_faiss_metadata()

# Create embeddings and save to FAISS
def create_embeddings(text, role, user_id=None, group_id=None):
    """Tạo embedding và lưu vào FAISS cùng metadata với thời gian đọc được."""

    # Tạo embedding từ văn bản
    embedding = model.encode([text], convert_to_numpy=True)
    embedding = np.array(embedding, dtype=np.float32)

    # Lưu vector vào FAISS
    index.add(embedding)

    # Lưu metadata với thông tin thời gian dễ đọc
    entry = {
        "role": role,
        "content": text,
        "user_id": user_id,
        "group_id": group_id,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Thời gian dễ đọc
    }
    metadata.append(entry)

    # Ghi log
    # print(f"Đã lưu vào FAISS: {text[:50]}...")  # Log nội dung (giới hạn 50 ký tự)
    # print(f"Đã lưu metadata: {entry}")

    # Lưu FAISS index và metadata ngay lập tức
    save_faiss_index(index)
    save_faiss_metadata(metadata)
# Search similar context
def search_similar_context(query, k=5):
    """
    Tìm kiếm ngữ cảnh tương tự từ FAISS mà không phân biệt user_id và group_id.
    """
    # Tạo embedding từ câu truy vấn
    query_embedding = model.encode([query], convert_to_numpy=True)
    query_embedding = np.array(query_embedding, dtype=np.float32)

    # Truy vấn FAISS
    D, I = index.search(query_embedding, k=k)

    # Lọc metadata (không lọc theo user_id hay group_id)
    results = []
    for j, i in enumerate(I[0]):
        if i < len(metadata):  # Đảm bảo index hợp lệ
            meta = metadata[i]
            results.append((meta, D[0][j]))  # Lưu metadata và độ tương tự

    return results




#GET CONTEXT FROM EACH USER OR EACH GROUP
def get_contexts(user_id, group_id, user_input, k=5):
    """
    Lấy ngữ cảnh chung từ FAISS mà không phân biệt user_id và group_id.
    """
    # Truy vấn ngữ cảnh từ FAISS (không phân biệt user_id và group_id)
    contexts = search_similar_context(user_input, k=k)  # Tìm kiếm ngữ cảnh từ FAISS mà không cần bộ lọc

    # Tạo danh sách messages từ ngữ cảnh
    messages = [{"role": context["role"], "content": context["content"]} for context, _ in contexts]

    # Thêm tin nhắn mới nhất của người dùng
    messages.append({"role": "user", "content": user_input})

    return messages



# Chat with AI
# Bộ nhớ lưu lịch sử cuộc trò chuyện
# Bộ nhớ ngắn hạn trong phiên hiện tại
conversation_history = []

def chat_with_ai(user_input, user_id=None, group_id=None):
    """
    Nhận đầu vào từ người dùng và gửi đến AI.
    Kết hợp ngữ cảnh cá nhân và nhóm để tạo phản hồi.
    """
    # Prompt định hướng phong cách trả lời
    system_prompt = (
        """
You are my AI
        """
    )


    # Lưu câu hỏi vào lịch sử cục bộ
    conversation_history.append({
        "role": "user",
        "content": user_input,
        "user_id": user_id,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")  # Lưu thời gian dễ đọc
    })

    # Lấy ngữ cảnh từ FAISS
    contexts = search_similar_context(user_input, k=5)  # Tìm kiếm ngữ cảnh từ FAISS mà không cần bộ lọc

    # Tạo danh sách messages (chỉ giữ `role` và `content`)
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend([{"role": context["role"], "content": context["content"]} for context, _ in contexts])
    messages.extend([{"role": msg["role"], "content": msg["content"]} for msg in conversation_history[-5:]])  # Giữ tối đa 5 tin nhắn gần nhất

    # Gửi yêu cầu đến API Groq
    completion = client.chat.completions.create(
        model="llama3-8b-8192",
        messages=messages,
        temperature=1,
        max_tokens=2048,
        top_p=1,
        stream=True,
    )

    # Nhận phản hồi từ API
    response = ""
    for chunk in completion:
        response += chunk.choices[0].delta.content or ""


    # Lưu phản hồi vào lịch sử cục bộ
    conversation_history.append({
        "role": "assistant",
        "content": response,
        "user_id": "bot",  # Bot không có user_id, đánh dấu bằng 'bot'
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    })

    return response



# --- TELEGRAM CLIENT ---
telegram_client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

@telegram_client.on(events.NewMessage)
async def handle_new_message(event):
    chat_id = event.chat_id
    user_id = event.sender_id

    
    if chat_id not in CHANNEL_WHITELIST:
        return
    # Phân biệt giữa tin nhắn cá nhân và nhóm
    group_id = chat_id if event.is_group or event.is_channel else None

    # Lấy nội dung tin nhắn
    message_text = event.text



    create_embeddings(message_text, role="user", user_id=user_id, group_id=group_id)


    # Lấy danh sách ngữ cảnh từ cá nhân và nhóm
    messages = get_contexts(user_id, group_id, message_text)

    # Gửi câu hỏi đến AI và nhận phản hồi
    response = chat_with_ai(user_input=message_text, user_id=user_id, group_id=group_id)

    # Gửi phản hồi đến Telegram
    await event.reply(response)


# Run the Telegram Client
async def main():
    print("Đang khởi chạy Telegram Client Bot...")
    async with telegram_client:
        await telegram_client.run_until_disconnected()

if __name__ == "__main__":
    try:
        telegram_client.loop.run_until_complete(main())
    finally:
        print("Bot đã dừng.")

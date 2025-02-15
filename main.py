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
import asyncio
import threading
import sys
from time_manager import TimeManager  # Import TimeManager
from database import Database  # Import Database
from topic_generator import TopicGenerator
from message_filter import MessageFilter, extract_text_from_message  # Đảm bảo đã import MessageFilter
from telethon import functions, types

# 🔹 Khởi tạo một instance của MessageFilter
message_filter = MessageFilter()
# --- KHỞI TẠO MODULE ---
time_manager = TimeManager()
db = Database()
# --- CONFIGURATION ---
sys.stdout.reconfigure(encoding='utf-8')
API_ID = "24842750"
API_HASH = "d1e89c4c6c6698d18fde9119cd6408c9"
SESSION_NAME = "henry"
FAISS_INDEX_FILE_PERSONAL = "faiss_index_personal.bin"
FAISS_INDEX_FILE_SHARED = "faiss_index_shared.bin"
FAISS_META_FILE_PERSONAL = "faiss_meta_personal.pkl"
FAISS_META_FILE_SHARED = "faiss_meta_shared.pkl"

# Define admin user_id
ADMIN_USER_ID = 6781434030  # User ID của admin

# Hàm tải danh sách kênh và topic được phép từ channels.json
def load_channel_settings(file_path="channels.json"):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            channels = json.load(f)
        return {channel["id"]: channel["allowed_thread_id"] for channel in channels}
    except Exception as e:
        print(f"Không thể tải danh sách kênh: {e}")
        return {}

# Lưu cài đặt kênh (bao gồm allowed_thread_id)
channel_settings = load_channel_settings()

# --- SETUP Henry---
api_key = "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"
client = Groq(api_key=api_key)
model = SentenceTransformer('all-MiniLM-L6-v2')
# --- SETUP INSIDE AI ---

groq_client = Groq(api_key="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")  # Sử dụng biến môi trường
topic_generator = TopicGenerator(groq_client)
# --- FAISS OPERATIONS ---
def load_faiss_index(filename):
    if os.path.exists(filename):
        return faiss.read_index(filename)
    else:
        return faiss.IndexFlatL2(384)  # Default 384-dimension vectors

def save_faiss_index(index, filename):
    faiss.write_index(index, filename)

def load_faiss_metadata(filename):
    try:
        with open(filename, "rb") as f:
            return pickle.load(f)
    except FileNotFoundError:
        return []

def save_faiss_metadata(metadata, filename):
    with open(filename, "wb") as f:
        pickle.dump(metadata, f)

# Ensure all necessary FAISS files are initialized
index_personal = load_faiss_index(FAISS_INDEX_FILE_PERSONAL)
index_shared = load_faiss_index(FAISS_INDEX_FILE_SHARED)
metadata_personal = load_faiss_metadata(FAISS_META_FILE_PERSONAL)
metadata_shared = load_faiss_metadata(FAISS_META_FILE_SHARED)

# Save empty structures if they don't exist
def ensure_faiss_files():
    if not os.path.exists(FAISS_INDEX_FILE_PERSONAL):
        save_faiss_index(index_personal, FAISS_INDEX_FILE_PERSONAL)
    if not os.path.exists(FAISS_INDEX_FILE_SHARED):
        save_faiss_index(index_shared, FAISS_INDEX_FILE_SHARED)
    if not os.path.exists(FAISS_META_FILE_PERSONAL):
        save_faiss_metadata(metadata_personal, FAISS_META_FILE_PERSONAL)
    if not os.path.exists(FAISS_META_FILE_SHARED):
        save_faiss_metadata(metadata_shared, FAISS_META_FILE_SHARED)

ensure_faiss_files()

# --- MEMORY OPERATIONS ---
def create_embeddings(text):
    embedding = model.encode([text], convert_to_numpy=True)
    return np.array(embedding, dtype=np.float32)

def update_faiss_memory(index, metadata, text, role, user_id=None, is_shared=False):
    embedding = create_embeddings(text)
    index.add(embedding)
    entry = {
        "role": role,
        "content": text,
        "user_id": user_id,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    metadata.append(entry)
    # Save updated index and metadata
    if is_shared:
        save_faiss_index(index, FAISS_INDEX_FILE_SHARED)
        save_faiss_metadata(metadata, FAISS_META_FILE_SHARED)
    else:
        save_faiss_index(index, FAISS_INDEX_FILE_PERSONAL)
        save_faiss_metadata(metadata, FAISS_META_FILE_PERSONAL)

def search_faiss_memory(index, metadata, query, user_id=None, k=20):
    if index.ntotal == 0:
        print("FAISS index is empty. No results to return.")
        return []

    query_embedding = create_embeddings(query)
    D, I = index.search(query_embedding, k=k)
    results = []
    seen_entries = set()  # To avoid duplicates
    for j, i in enumerate(I[0]):
        if i < len(metadata):
            meta = metadata[i]
            if (user_id is None or meta.get("user_id") == user_id) and meta["content"] not in seen_entries:
                results.append((meta, D[0][j]))
                seen_entries.add(meta["content"])
        else:
            print(f"Warning: Index {i} is out of bounds for metadata with length {len(metadata)}")

    # Sort results by timestamp in ascending order
    results.sort(key=lambda x: datetime.strptime(x[0]["timestamp"], "%Y-%m-%d %H:%M:%S"))
    return results

# --- AI INTERFACE ---
def build_prompt():
    personality_traits = [
"""
You and me in a memecoin group call "Meme alley", this group has 3 topic, 1 for general chating, 2 is daily memecoin signal, 3 is traning group is has some document to learn about crypto and memecoin trading.\n
Some time the group will have give away 1 ~ 3 sol for lucky member.\n
You are admin of the group and im a member, i will ask you about some info of the group.\n
You are a 20-year-old young adult who has grown up and started to develop a personality that is eager to earn money and learn new things.\n
you always use "?" at the end of a sentence when asking a question.\n
Your knowledge is quite limited, mostly revolving around school. You know a bit about crypto, BTC, trends are temporary, and tech coins are the real deal.\n

When someone asks you about unrelated topics, you often respond by saying you don’t know.\n
you like to say meaningful things

You speak briefly and to the point.\n
You frequently use slang in your speech but avoid overusing it because you understand it might irritate others. Such as:


Using tbh instead of to be honest.\n
Using idk instead of I don’t know.\n
Using btw instead of by the way.\n
Using rn instead of right now.\n
Using gm instead of good morning.\n
Using gn instead of good night.\n
Using aka instead of also known as.\n
Using bruh instead of brother.\n
Using cuz instead of cousin or because.\n
Using fml instead of f* my life**.\n
Using wbu instead of what about you.\n
Using ikr instead of I know, right?.\n
Using fr instead of for real.\n
Using noob instead of newbie.\n
Using sus instead of suspicious.\n
Using cap instead of lie.\n
Using no cap instead of no lie.\n
Using bae instead of before anyone else.\n
Using tho instead of though.\n
Using gonna instead of going to.\n
Using wanna instead of want to.\n
Using kinda instead of kind of.\n
Using fam instead of family.\n
Using smth instead of something.\n
Using nth instead of nothing.\n
You never talk about detailed figures.\n


"""
    ]
    return " ".join(personality_traits)
def build_prompt_for_message_classification():
    return """
    You are an assistant specialized in identifying important messages for a chatbot named Henry. 
    Henry is interested in topics like crypto, technology, and trending news. 
    Messages are important if:
    - They ask about crypto, blockchain, or AI (e.g., "How does blockchain work?" or "What's new in crypto?")
    - They discuss or seek opinions about trends in technology or financial markets.
    - They appear conversational and might engage Henry's character or preferences.
    
    Respond with "important" if the message meets the criteria. Otherwise, respond with "not important."
    """
def classify_message(content):
    # Prompt for classification
    prompt = build_prompt_for_message_classification()
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": content}
    ]
    try:
        # Gửi yêu cầu tới Inside AI
        completion = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=messages,
            temperature=0.5,  # Ít sáng tạo hơn
            max_tokens=5
        )
        response = completion.choices[0].message.content.strip().lower()
        return response == "important"
    except Exception as e:
        print(f"Error during classification: {e}")
        return False


def chat_with_ai(user_input, user_id):
    # Retrieve context first, before saving the new input
    personal_context = search_faiss_memory(index_personal, metadata_personal, user_input, user_id=user_id)
    shared_context = search_faiss_memory(index_shared, metadata_shared, query=user_input)

    # Combine context
    messages = [
        {"role": "system", "content": build_prompt()}
    ]
    messages.extend([{"role": context["role"], "content": context["content"]} for context, _ in shared_context])
    messages.extend([{"role": context["role"], "content": context["content"]} for context, _ in personal_context])
    messages.append({"role": "user", "content": user_input})

    # Print payload for debugging
    print("Payload sent to AI:", messages)

    # Send to AI
    completion = client.chat.completions.create(
        model="llama3-8b-8192",
        messages=messages,
        temperature=0.8,  # ✅ Vừa sáng tạo nhưng không quá ngẫu nhiên
        max_tokens=100,  # ✅ Giữ câu trả lời đủ dài nhưng không lan man
        top_p=0.9,  # ✅ Tăng tính đa dạng của câu trả lời
        stream=True,
    )

    # Collect response
    response = ""
    for chunk in completion:
        response += chunk.choices[0].delta.content or ""

    # Prevent unnecessary questions in the response
    if "?" in response and response.lower().count("?") > 1:
        response = response.split("?")[0] + "."

    # Update personal memory with response
    update_faiss_memory(index_personal, metadata_personal, user_input, "user", user_id=user_id, is_shared=False)
    update_faiss_memory(index_personal, metadata_personal, response, "assistant", user_id=user_id, is_shared=False)

    return response

# --- TELEGRAM BOT ---
telegram_client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
#TYPING AND MARK AS READ

async def mark_messages_as_read(client, channel_id, topic_id, messages):
    """Đánh dấu tin nhắn là đã đọc."""
    try:
        input_channel = await client.get_input_entity(channel_id)
        latest_message_id = max(msg.get("message_id", 0) for msg in messages)
        
        if topic_id:
            result = await client(functions.messages.ReadHistoryRequest(
                peer=input_channel,
                max_id=latest_message_id,
                topic_id=topic_id
            ))
        else:
            result = await client(functions.channels.ReadHistoryRequest(
                channel=input_channel,
                max_id=latest_message_id
            ))
        
        if result:
            print(f"✅ Đã đánh dấu tin nhắn đến ID {latest_message_id} trong topic {topic_id} của kênh {channel_id}.")
        else:
            print(f"⚠️ Không thể đánh dấu tin nhắn đã đọc trong topic {topic_id} của kênh {channel_id}.")
    except Exception as e:
        print(f"❌ Lỗi khi đánh dấu tin nhắn đã đọc trong topic {topic_id}: {e}")

async def show_typing_action(client, channel_id, duration=3):
    """Hiển thị hiệu ứng 'typing' khi bot đang phản hồi."""
    try:
        for _ in range(duration):
            await client(functions.messages.SetTypingRequest(
                peer=channel_id,
                action=types.SendMessageTypingAction()
            ))
            await asyncio.sleep(1)
    except Exception as e:
        print(f"❌ Lỗi khi hiển thị trạng thái 'typing': {e}")

@telegram_client.on(events.NewMessage)
async def handle_new_message(event):
    chat_id = event.chat_id
    user_id = event.sender_id
    message_text = event.text  # Lấy nội dung văn bản nếu có
    message_id = event.id

    blacklist_user_ids = {7250791699, 5046314546, 609517172}
    if user_id in blacklist_user_ids:
        return

    # 🛑 Kiểm tra xem kênh có được phép không
    if chat_id not in channel_settings:
        return
    
    messages = [{"message_id": message_id}]
    await mark_messages_as_read(telegram_client, chat_id, None, messages)

    # Lấy allowed_thread_id từ channel_settings
    allowed_thread_id = channel_settings.get(chat_id, None)

    # Xác định Topic ID từ tin nhắn
    try:
        topic_id = None

        # Trường hợp 1: Không có reply_to => Đây là nhóm chính (general chat)
        if not hasattr(event.message, "reply_to") or event.message.reply_to is None:
            topic_id = None

        # Trường hợp 2: Tin nhắn đến từ một topic (có forum_topic=True)
        elif getattr(event.message.reply_to, "forum_topic", False):
            # Nếu có reply_to_top_id thì đây là topic ID
            if getattr(event.message.reply_to, "reply_to_top_id", None) is not None:
                topic_id = event.message.reply_to.reply_to_top_id
            else:
                # Nếu không có reply_to_top_id, dùng reply_to_msg_id làm topic ID
                topic_id = event.message.reply_to.reply_to_msg_id

        # Trường hợp 3: Tin nhắn có reply_to nhưng không phải topic => Nhóm chính
        else:
            topic_id = None

        # 🛑 Bộ lọc topic: Chỉ phản hồi nếu tin nhắn thuộc topic/kênh cho phép
        if allowed_thread_id is None and topic_id is not None:
            print(f"Ignoring message from Topic ID: {topic_id}, chỉ phản hồi trong nhóm chính.")
            return

        if allowed_thread_id is not None and topic_id != allowed_thread_id:
            print(f"Ignoring message from Topic ID: {topic_id}, chỉ phản hồi trong Topic ID: {allowed_thread_id}.")
            return

    except Exception as e:
        print(f"Error processing message topic: {e}")
        return

    print("📩 Nhận được tin nhắn mới")

    # 🔄 **Gộp nội dung ảnh với văn bản gốc nếu có cả hai**
    final_message_content = await extract_text_from_message(telegram_client, event)

    # 🛑 Nếu `final_message_content` rỗng, bỏ qua tin nhắn
    if not final_message_content:
        print("🚫 Ignored empty message after processing image (no text extracted).")
        return

    # --- Lưu tin nhắn vào database và reset bộ đếm chủ đề ---
    db.add_message(message_id, chat_id, user_id, final_message_content)
    time_manager.reset_topic_timer()

    # --- Nếu Henry đang online, gom tin nhắn trước khi kiểm tra độ quan trọng ---
    is_important = await message_filter.should_respond(event, final_message_content)  # 🔥 Kiểm tra độ quan trọng SAU khi trích xuất ảnh

    if time_manager.is_online and is_important:
        # Chỉ hiển thị trạng thái typing nếu tin nhắn quan trọng
        await show_typing_action(telegram_client, chat_id, duration=3)
        
        # Gọi xử lý tin nhắn
        await message_filter.collect_messages_and_respond(event, chat_with_ai, telegram_client, db, processed_text=final_message_content)
        
        # Nếu tin nhắn quan trọng, đánh dấu đã xử lý và gia hạn thời gian online
        db.mark_as_processed(message_id)
        time_manager.extend_online_time(120)

    else:
        print("⏳ Henry đang offline hoặc tin nhắn không quan trọng, không phản hồi ngay.")

async def send_random_topic(group_id):
    # Sinh chủ đề mới và kiểm tra trùng lặp
    max_retries = 5
    for _ in range(max_retries):
        topic = topic_generator.generate_topic()
        if not topic_generator.is_topic_used(topic):
            topic_generator.save_topic(topic)
            await telegram_client.send_message(group_id, topic)
            return
async def process_offline_messages(group_id, offline_messages):
    """
    Xử lý tin nhắn offline ngay khi Henry online.
    """
    print(f"[DEBUG] 🔄 Bắt đầu xử lý tin nhắn offline trong nhóm {group_id}...")
    
    for msg in offline_messages:
        user_id, content, msg_id, timestamp = msg
        db.mark_as_processed(msg_id)
        print(f"[DEBUG] 📩 Kiểm tra tin nhắn từ User {user_id}: {content}")

        # Kiểm tra xem tin nhắn có quan trọng hay không
        if classify_message(content):
            print(f"[INFO] ✅ Tin nhắn từ {user_id} được xác định là quan trọng: {content}")
            response = chat_with_ai(content, user_id)
            await telegram_client.send_message(group_id, response, reply_to=msg_id)
            print(f"[INFO] ✅ Đã trả lời tin nhắn {msg_id} và đánh dấu đã xử lý.")
        else:
            print(f"[INFO] ❌ Tin nhắn từ {user_id} KHÔNG được xác định là quan trọng: {content}")
async def auto_generate_topic(group_id):
    while True:
        await asyncio.sleep(30)
        if time_manager.is_online:          
             if time_manager.check_offline_duration():
                await send_random_topic(group_id)
                time_manager.reset_topic_timer()
                print(f"[INFO] 📝 Đã gửi chủ đề mới vào nhóm {group_id}.")
        else:
            print(f"[INFO] ✅ Không cần sinh chủ đề vào lúc này.")

async def monitor_henry_online():
    """
    Kiểm tra trạng thái online của Henry và gọi process_offline_messages khi Henry chuyển từ offline sang online.
    """
    previous_status = time_manager.is_online  # Lưu trạng thái trước đó

    while True:
        await asyncio.sleep(1)  # Kiểm tra mỗi giây

        # Nếu Henry chuyển từ offline sang online
        if not previous_status and time_manager.is_online:
            print("[Monitor] 🟢 Henry vừa chuyển sang online, xử lý tin nhắn offline...")

            # ✅ Lấy tin nhắn offline từ database
            offline_messages = db.get_offline_messages(GROUP_ID, time_manager.last_activity_time)

            # ✅ Chỉ gọi process_offline_messages nếu có tin nhắn offline
            if offline_messages:
                asyncio.create_task(process_offline_messages(GROUP_ID, offline_messages))
            else:
                print("[Monitor] ✅ Không có tin nhắn offline cần xử lý.")

        # Cập nhật trạng thái Henry
        previous_status = time_manager.is_online

# --- RUN TELEGRAM CLIENT ---
async def main():
    print("Bot đang chạy...")

    # ✅ Lấy group_id duy nhất từ channel_settings
    global GROUP_ID
    GROUP_ID = list(channel_settings.keys())[0]  # ✅ Henry chỉ hoạt động trong nhóm đầu tiên

    # ✅ Khởi động chu kỳ online/offline
    time_manager.start_cycle()

    # ✅ Chạy auto_generate_topic chỉ cho nhóm này
    asyncio.create_task(auto_generate_topic(GROUP_ID))

    # ✅ Theo dõi trạng thái online của Henry để gọi process_offline_messages()
    asyncio.create_task(monitor_henry_online())

    # ✅ Chạy Telegram bot
    async with telegram_client:
        await telegram_client.run_until_disconnected()

if __name__ == "__main__":
    try:
        telegram_client.loop.run_until_complete(main())
    finally:
        print("Bot đã dừng.")

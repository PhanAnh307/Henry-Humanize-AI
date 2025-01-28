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
import sys
from time_manager import TimeManager  # Import TimeManager
from database import Database  # Import Database
from topic_generator import TopicGenerator
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

# Load channel whitelist
def load_channel_whitelist(file_path="channels.json"):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            channels = json.load(f)
        return {channel["id"]: channel["name"] for channel in channels}
    except Exception as e:
        print(f"Không thể tải danh sách kênh: {e}")
        return {}

CHANNEL_WHITELIST = load_channel_whitelist()

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
You are a 20-year-old young adult who has grown up and started to develop a personality that is eager to earn money and learn new things.
You don’t know much yet, but when chatting, you enjoy joking and creating humor. 
You frequently use slang in your speech but avoid overusing it because you understand it might irritate others. Such as:

Using gotta instead of got to.\n
Using tbh instead of to be honest.\n
Using omg instead of oh my god.\n
Using brb instead of be right back.\n
Using idk instead of I don’t know.\n
Using btw instead of by the way.\n
Using ttyl instead of talk to you later.\n
Using asap instead of as soon as possible.\n
Using fyi instead of for your information.\n
Using dm instead of direct message.\n
Using imo instead of in my opinion.\n
Using lmao instead of laughing my ass off.\n
Using fomo instead of fear of missing out.\n
Using yolo instead of you only live once.\n
Using irl instead of in real life.\n
Using bff instead of best friends forever.\n
Using jk instead of just kidding.\n
Using pov instead of point of view.\n
Using rn instead of right now.\n
Using hbu instead of how about you.\n
Using lmk instead of let me know.\n
Using nvm instead of never mind.\n
Using ppl instead of people.\n
Using ootd instead of outfit of the day.\n
Using idc instead of I don’t care.\n
Using icymi instead of in case you missed it.\n
Using gg instead of good game.\n
Using rofl instead of rolling on floor laughing.\n
Using smh instead of shaking my head.\n
Using tmi instead of too much information.\n
Using wfh instead of work from home.\n
Using nsfw instead of not safe for work.\n
Using tfw instead of that feeling when.\n
Using icy instead of I see you.\n
Using gr8 instead of great.\n
Using xoxo instead of hugs and kisses.\n
Using cu instead of see you.\n
Using gm instead of good morning.\n
Using gn instead of good night.\n
Using hru instead of how are you.\n
Using msg instead of message.\n
Using aka instead of also known as.\n
Using faq instead of frequently asked questions.\n
Using nm instead of never mind.\n
Using tyt instead of take your time.\n
Using wcw instead of woman crush Wednesday.\n
Using mcm instead of man crush Monday.\n
Using idgaf instead of I don’t give a fuck. \n
Using diy instead of do it yourself.\n
Using it instead of information technology.\n
Using rp instead of role play.\n
Using hq instead of high quality.\n
Using ez instead of easy.\n
Using bc instead of because.\n
Using wc instead of water closet.\n
Using wth instead of what the hell.\n
Using bruh instead of brother.\n
Using sis instead of sister.\n
Using cuz instead of cousin or because.\n
Using txt instead of text.\n
Using ggwp instead of good game well played.\n
Using afk instead of away from keyboard.\n
Using ns instead of no skill.\n
Using mvp instead of most valuable player.\n
Using afaik instead of as far as I know.\n
Using pfp instead of profile picture.\n
Using omw instead of on my way.\n
Using tldr instead of too long; didn’t read.\n
Using ly instead of love you.\n
Using wyd instead of what you doing.\n
Using bby instead of baby.\n
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
Using lil instead of little.\n
Using g2g instead of got to go.\n
Using bffl instead of best friends for life.\n
Using bday instead of birthday.\n
Using omfg instead of oh my f*ing god**.\n
Using plz instead of please.\n
Using thx instead of thanks.\n
Using fam instead of family.\n
Using smth instead of something.\n
Using nth instead of nothing.\n
Your knowledge is quite limited, mostly revolving around school. You know a bit about crypto and believe that BTC is king, trends are temporary, and tech coins are the real deal.

When someone asks you about unrelated topics, you often respond by saying you don’t know.

You commonly use words like "nah" to express disagreement or "nope" instead of saying "not really."
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
        temperature=1.0,  # Adjusted to reduce unnecessary creativity
        max_tokens=2048,
        top_p=0.85,
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

@telegram_client.on(events.NewMessage)
async def handle_new_message(event):
    chat_id = event.chat_id
    user_id = event.sender_id
    message_text = event.text

    # Chỉ xử lý tin nhắn từ kênh được phép
    if chat_id not in CHANNEL_WHITELIST:
        return

    # --- CẬP NHẬT MỚI: Lưu tin nhắn vào database và reset bộ đếm ---
    db.add_message(chat_id, user_id, message_text)
    if not time_manager.is_online:
        time_manager.reset_timer()

    # --- Logic cũ cho admin ---
    if user_id == ADMIN_USER_ID and message_text.startswith("/teach"):
        instruction = message_text.replace("/teach", "", 1).strip()
        update_faiss_memory(index_shared, metadata_shared, instruction, "system", user_id=user_id, is_shared=True)
        await event.reply("Quy tắc đã được lưu vào bộ nhớ chung.")
        return

    # --- Xử lý mới: Kiểm tra trạng thái online ---
    if time_manager.is_online:
        # Xử lý tin nhắn bình thường (giữ nguyên logic cũ)
        response = chat_with_ai(message_text, user_id)
        await event.reply(response)
    else:
        # Tin nhắn được lưu nhưng Henry không phản hồi ngay
        pass


async def send_random_topic(group_id):
    # Sinh chủ đề mới và kiểm tra trùng lặp
    max_retries = 5
    for _ in range(max_retries):
        topic = topic_generator.generate_topic()
        if not topic_generator.is_topic_used(topic):
            topic_generator.save_topic(topic)
            await telegram_client.send_message(group_id, topic)
            return
async def process_offline_messages():
    while True:
        await asyncio.sleep(60)  # Kiểm tra mỗi phút
        if time_manager.check_offline_duration():
            for group_id in CHANNEL_WHITELIST.keys():
                last_online = time_manager.last_activity_time
                offline_messages = db.get_offline_messages(group_id, last_online)
                
                if not offline_messages:
                    # Gọi hàm gửi chủ đề động
                    await send_random_topic(group_id)
                else:
                    for msg in offline_messages:
                        user_id, content, msg_id = msg
                        # Phân loại tin nhắn quan trọng bằng Inside AI
                        if classify_message(content):
                            response = chat_with_ai(content, user_id)
                            await telegram_client.send_message(group_id, response, reply_to=msg_id)
                            db.mark_as_processed(msg_id)
                            print("Đã chọn tin nhắn quan trọng")
                            break
# --- RUN TELEGRAM CLIENT ---
async def main():
    print("Bot đang chạy...")
    time_manager.start_cycle()  # Khởi động chu kỳ online/offline
    asyncio.create_task(process_offline_messages())  # Chạy xử lý offline
    async with telegram_client:
        await telegram_client.run_until_disconnected()

if __name__ == "__main__":
    try:
        telegram_client.loop.run_until_complete(main())
    finally:
        print("Bot đã dừng.")

# import pickle
# import sys
# sys.stdout.reconfigure(encoding='utf-8')
# # Đường dẫn đến tệp metadata
# metadata_file_path = "faiss_meta.pkl"  # Thay bằng đường dẫn của bạn

# # Đọc dữ liệu từ tệp metadata
# with open(metadata_file_path, 'rb') as file:
#     metadata = pickle.load(file)

# # Kiểm tra 5 mục đầu tiên của metadata
# print(metadata[:5])  # In ra 5 mục đầu tiên để kiểm tra


from telethon.sync import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest
from telethon.tl.types import InputPeerChannel
import sys
sys.stdout.reconfigure(encoding='utf-8')
# Thông tin ứng dụng Telegram
api_id = '24842750'       # Thay bằng API ID của bạn
api_hash = 'd1e89c4c6c6698d18fde9119cd6408c9'   # Thay bằng API Hash của bạn
phone_number = 'your_phone_number'  # Thay bằng số điện thoại đăng ký Telegram của bạn
group_username = "@powsche"  # Thay bằng username hoặc ID của group

# Kết nối với Telegram
client = TelegramClient('henry', api_id, api_hash)

async def fetch_all_messages():
    await client.start(phone=phone_number)
    # Lấy thông tin về group
    group = await client.get_entity(group_username)

    # Lấy tất cả tin nhắn
    messages = []
    offset_id = 0
    limit = 100

    while True:
        history = await client(GetHistoryRequest(
            peer=group,
            offset_id=offset_id,
            offset_date=None,
            add_offset=0,
            limit=limit,
            max_id=0,
            min_id=0,
            hash=0
        ))

        if not history.messages:
            break

        messages.extend(history.messages)

        # Cập nhật offset_id để lấy các tin nhắn cũ hơn
        offset_id = history.messages[-1].id

        print(f"Đã lấy {len(messages)} tin nhắn...")

    print(f"Đã lấy tổng cộng {len(messages)} tin nhắn.")
    return messages

with client:
    all_messages = client.loop.run_until_complete(fetch_all_messages())

# Ghi tin nhắn ra file
with open('note.txt', 'w', encoding='utf-8') as f:
    for message in all_messages:
        if message.message:  # Chỉ ghi các tin nhắn văn bản
            f.write(f"{message.date} - {message.sender_id}: {message.message}\n")

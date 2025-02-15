import asyncio
import re
import json
from datetime import datetime, timedelta
from groq import Groq
from PIL import Image
import pytesseract
import os
from paddleocr import PaddleOCR
import cv2
class MessageFilter:
    def __init__(self):
        self.bot_user_id = 6781434030  # 🔹 Ghi trực tiếp User ID của bot
        self.groq_api_key = "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"  # 🔹 Ghi trực tiếp API Key
        self.groq_client = Groq(api_key=self.groq_api_key)
        self.last_messages = {}
        self.last_henry_message = {}  # 🔹 Lưu tin nhắn cuối cùng của Henry
        self.user_replied_to_henry = {}  # 🔹 Theo dõi nếu user đã trả lời câu hỏi của Henry

    async def should_respond(self, event, combined_message):
        """
        Xác định xem tin nhắn có quan trọng không.
        """
        user_id = event.sender_id
        if not combined_message:
            return False  # Không có tin nhắn nào để xử lý

        print(f"[DEBUG] 🔍 Đang kiểm tra tin nhắn: {combined_message}")
        print(f"[DEBUG] 📌 Tin nhắn cuối cùng của Henry: {self.last_henry_message.get(user_id, 'Không có')}")
        print(f"[DEBUG] ⏳ User đã trả lời Henry chưa? {self.user_replied_to_henry.get(user_id, False)}")

        previous_henry_message = self.last_henry_message.get(user_id, None)
        user_replied = self.user_replied_to_henry.get(user_id, False)

        if previous_henry_message and "?" in previous_henry_message and not user_replied:
            print(f"[Filter] ✅ Tin nhắn này là phản hồi cho câu hỏi trước đó của Henry: {combined_message}")
            self.user_replied_to_henry[user_id] = True
            return True

        if re.search(r"@henryyyy\b", combined_message, re.IGNORECASE):
            print("[Filter] ✅ Tin nhắn có mention @henryyyy, nên trả lời.")
            return True

        print(f"[Filter] 📩 Xác định tin nhắn quan trọng: {combined_message}")

        is_important = await self.is_important_message(combined_message)
        return is_important

    async def is_important_message(self, content):
        """
        Gửi tin nhắn đã gom đến AI để xác định có quan trọng hay không.
        """
        prompt = """
        You are an AI specialized in classifying messages for chatbot Henry.
        Henry only responds to important messages, including:
        - Questions about technology, AI, blockchain, crypto.
        - Questions or requests for personal feedback.
        - Open discussion topics.
        - Messages that are significant for the group.
        - Short talk
        - Greeting
        - About group chat
        - Good morning or good night

        Respond "important" if the message contains content about the above topics, otherwise return "not important". Dont say anything else just "important" or "not important"

        """

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": content}
        ]

        try:
            completion = self.groq_client.chat.completions.create(
                model="llama3-8b-8192",
                messages=messages,
                temperature=0.5,
                max_tokens=3
            )
            response = completion.choices[0].message.content.strip().lower()
            response = re.sub(r"[^a-z ]", "", response).strip()

            print(f"[DEBUG] 🧠 AI Response: {response}")
            
            return response == "important"
        except Exception as e:
            print(f"[ERROR] ❌ AI request failed: {e}")
            return False


    async def collect_messages_and_respond(self, event, chat_with_ai, telegram_client, db, processed_text=None):
        """
        Collect messages for 5 seconds before deciding whether to respond.
        """
        user_id = event.sender_id
        chat_id = event.chat_id
        message_text = processed_text if processed_text is not None else event.text.strip()
        message_id = event.id  # Lấy ID của tin nhắn

        print(f"[DEBUG] 📩 Nhận tin nhắn mới từ User {user_id}: {message_text}")

        # Thêm tin nhắn vào bộ nhớ đệm của user
        if user_id not in self.last_messages:
            self.last_messages[user_id] = []
        self.last_messages[user_id].append(message_text)

        # Nếu đây là tin nhắn đầu tiên, chờ 5 giây để thu thập tin nhắn tiếp theo
        if len(self.last_messages[user_id]) == 1:
            await asyncio.sleep(5)

        # Sau 5 giây, gom toàn bộ tin nhắn thành một câu
        combined_message = " ".join(self.last_messages[user_id])

        print(f"[DEBUG] 🔄 Tin nhắn đã gom: {combined_message}")

        # Kiểm tra xem tin nhắn đã gom có quan trọng không
        if await self.should_respond(event, combined_message):
            response = chat_with_ai(combined_message, user_id)
            
            # 🔹 Cập nhật tin nhắn cuối cùng của Henry ngay khi gửi tin nhắn
            self.last_henry_message[user_id] = response
            self.user_replied_to_henry[user_id] = False  # Reset trạng thái trả lời của user
            
            await telegram_client.send_message(chat_id, response)
            print(f"[Filter] ✅ Trả lời tin nhắn từ User {user_id}: {combined_message}")
        else:
            print(f"[Filter] ❌ Tin nhắn từ User {user_id} không đủ quan trọng để trả lời.")
        
        # 🔹 Đánh dấu tin nhắn đã được xử lý, ngay cả khi không quan trọng
        db.mark_as_processed(message_id)
        
        # Xóa tin nhắn đã xử lý khỏi bộ nhớ đệm
        self.last_messages[user_id] = []
ocr = PaddleOCR(use_angle_cls=True, lang='en')  # PaddleOCR hỗ trợ tốt hơn

def preprocess_image(image_path):
    """Tiền xử lý ảnh để tăng độ chính xác của OCR"""
    if not isinstance(image_path, str) or not os.path.exists(image_path):
        raise ValueError(f"[ERROR] Không thể tải ảnh: {image_path}")
    
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"Không thể đọc ảnh từ đường dẫn: {image_path}")
    
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)  # Chuyển sang grayscale
    
    # Tăng độ tương phản bằng adaptive threshold
    processed = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    
    return processed

def extract_text_from_image(image_path):
    """Trích xuất văn bản từ ảnh bằng cả Tesseract OCR và PaddleOCR"""
    try:
        processed_image = preprocess_image(image_path)
        
        # OCR bằng Tesseract
        text_tesseract = pytesseract.image_to_string(processed_image, lang='eng', config='--psm 6')
        
        # OCR bằng PaddleOCR
        result = ocr.ocr(image_path, cls=True)
        text_paddle = " ".join([line[1][0] for line in result[0] if line[1][1] > 0.5])
        
        # Kết hợp kết quả của cả hai OCR
        final_text = text_paddle if text_paddle else text_tesseract
        
        print(f"[OCR] Extracted Text: {final_text}")
        return final_text.strip()
    except Exception as e:
        print(f"[OCR] Lỗi khi trích xuất văn bản: {e}")
        return ""

async def extract_text_from_message(client, event):
    """Trích xuất văn bản từ ảnh trong tin nhắn và gộp với nội dung văn bản nếu có."""
    text_from_image = ""
    text_from_message = event.text.strip() if event.text else ""
    
    if event.photo:
        try:
            image_path = await client.download_media(event.photo)  # Thêm `await`
            if not isinstance(image_path, str) or not os.path.exists(image_path):
                raise ValueError(f"[ERROR] Không thể tải ảnh: {image_path}")
            
            text_from_image = extract_text_from_image(image_path)
            os.remove(image_path)  # Xóa ảnh sau khi xử lý
            print(f"[OCR] Đã xóa ảnh sau khi xử lý: {image_path}")
        except Exception as e:
            print(f"[ERROR] Lỗi khi xử lý ảnh: {e}")
    
    # Gộp nội dung ảnh + văn bản tin nhắn
    final_text = f"{text_from_image} {text_from_message}".strip()
    return final_text if final_text else None

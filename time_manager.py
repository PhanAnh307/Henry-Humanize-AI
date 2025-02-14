import threading
import time
from datetime import datetime
from database import Database
import asyncio
db = Database()
class TimeManager:
    def __init__(self):
        self.timer = None  # Bộ đếm online/offline
        self.is_online = False  # Trạng thái online của Henry
        self.last_activity_time = datetime.now()  # Lần hoạt động cuối
        
        # ✅ Bắt đầu bộ đếm kiểm tra chủ đề tự động sau 2 tiếng (7200 giây)
        self.topic_timer = threading.Timer(7200, self.check_offline_duration)
        self.topic_timer.start()
        
        # ✅ Bắt đầu luồng hiển thị thời gian mỗi giây
        self.status_thread = threading.Thread(target=self.log_status, daemon=True)
        self.status_thread.start()

    def start_cycle(self):
        self.switch_offline()
    def switch_online(self):
        """Chuyển Henry sang trạng thái online."""
        self.is_online = True
        print("[Time Manager] ✅ Henry đang online...")

        # ✅ Bộ đếm thời gian online, sẽ chuyển Henry về offline sau 10 phút
        self.timer = threading.Timer(600, self.switch_offline)
        self.timer.start()
    def switch_offline(self):
        """Chuyển Henry sang trạng thái offline."""
        self.is_online = False
        self.last_activity_time = datetime.now()  # ✅ Cập nhật thời gian offline gần nhất
        print(f"[Time Manager] ❌ Henry đang offline... (Lưu thời gian offline: {self.last_activity_time})")
        
        # Bộ đếm thời gian offline, sẽ chuyển Henry về online sau 5 phút (300 giây)
        self.timer = threading.Timer(20, self.switch_online)
        self.timer.start()

    def reset_timer(self):
        """Reset thời gian online/offline nếu cần."""
        if not self.is_online:
            if self.timer:
                self.timer.cancel()
            self.last_activity_time = datetime.now()
            self.start_cycle()

    def extend_online_time(self, extra_seconds):
        """Kéo dài thời gian online thêm `extra_seconds` giây nếu đang online."""
        if self.is_online and self.timer:
            self.timer.cancel()  # ❌ Hủy bộ đếm cũ
            self.timer = threading.Timer(self.timer.interval + extra_seconds, self.switch_offline)
            self.timer.start()
            print(f"[Time Manager] ⏳ Henry đang online, cộng thêm {extra_seconds / 60:.2f} phút.")

    def reset_topic_timer(self):
        """Reset bộ đếm chủ đề về 2 tiếng khi có tin nhắn mới."""
        if self.topic_timer:
            self.topic_timer.cancel()  # ❌ Hủy bộ đếm cũ nếu còn chạy
        
        # ✅ Đặt lại bộ đếm chủ đề mới (2 tiếng)
        self.topic_timer = threading.Timer(7200, self.check_offline_duration)
        self.topic_timer.start()
        print(f"[Time Manager] 🔄 Reset bộ đếm đang chạy")

    def check_offline_duration(self):
        """Kiểm tra xem đã đủ thời gian để gửi chủ đề tự động chưa."""
        remaining_time = self.topic_timer.interval - (datetime.now() - self.last_activity_time).total_seconds()

        if remaining_time <= 0:
            print("[Time Manager] ⏳ Hàm check_offline_duration đang chạy ...")
            # Gọi hàm gửi chủ đề tự động (tích hợp vào process_offline_messages)
            return True

    def log_status(self):
        """Luồng chạy liên tục để hiển thị thời gian online/offline còn lại."""
        while True:
            if self.timer and not self.timer.finished:
                remaining_time = self.timer.interval - (datetime.now() - self.last_activity_time).total_seconds()
                if self.is_online:
                    print(f"[Time Manager] ⏳ Henry đang ONLINE, sẽ OFFLINE sau {max(remaining_time, 0):.2f} giây.")
                else:
                    print(f"[Time Manager] ⏳ Henry đang OFFLINE, sẽ ONLINE sau {max(remaining_time, 0):.2f} giây.")
            time.sleep(1)  # ✅ Cập nhật mỗi giây

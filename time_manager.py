# time_manager.py
from datetime import datetime, timedelta
import threading

class TimeManager:
    def __init__(self):
        self.timer = None
        self.is_online = False
        self.last_activity_time = datetime.now()

    def start_cycle(self):
        self.switch_offline()

    def switch_online(self):
        self.is_online = True
        print("[Time Manager] Henry đang online...")
        self.timer = threading.Timer(60, self.switch_offline)  # 15 phút
        self.timer.start()

    def switch_offline(self):
        self.is_online = False
        print("[Time Manager] Henry đang offline...")
        self.timer = threading.Timer(30, self.switch_online)  # 30 phút
        self.timer.start()

    def reset_timer(self):
        # Chỉ reset timer nếu đang OFFLINE
        if not self.is_online:
            if self.timer:
                self.timer.cancel()
            self.last_activity_time = datetime.now()
            self.start_cycle()

    def check_offline_duration(self):
        offline_duration = datetime.now() - self.last_activity_time
        return offline_duration > timedelta(hours=2)
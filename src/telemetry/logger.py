import logging
import json
import os
from datetime import datetime
from typing import Any, Dict

class IndustryLogger:
    """
    Structured logger that simulates industry practices.
    Logs to both console and a file in JSON format.
    """
    def __init__(self, name: str = "AI-Lab-Agent", log_dir: str = "logs"):
        self.logger = logging.getLogger(name)
        # Thay vì in ra console (StreamHandler), chúng ta chỉ ghi log vào file
        self.logger.setLevel(logging.INFO)
        
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        # File Handler (JSON)
        log_file = os.path.join(log_dir, f"{datetime.now().strftime('%Y-%m-%d')}.log")
        file_handler = logging.FileHandler(log_file)
        
        # Chỉ giữ lại FileHandler, xóa StreamHandler nếu có
        if self.logger.hasHandlers():
            self.logger.handlers.clear()
            
        self.logger.addHandler(file_handler)

    def log_event(self, event_type: str, data: Dict[str, Any]):
        payload = {
            "timestamp": datetime.now().isoformat(),
            "event": event_type,
            "data": data
        }
        
        self.logger.info(json.dumps(payload))

    def info(self, msg: str):
        self.logger.info(msg)

    def error(self, msg: str, exc_info=True):
        self.logger.error(msg, exc_info=exc_info)

# Global logger instance
logger = IndustryLogger()

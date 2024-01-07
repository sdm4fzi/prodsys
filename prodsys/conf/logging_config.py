import logging
import sys
import logging.config
from datetime import datetime
from typing import Literal, Optional
import os

LOG_FILE_PATH = f'logs/prodsys_debug_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
CONFIG_LOCATION = os.path.join(os.path.dirname(__file__), "logging.ini")

logging_handler_dict = {
    "console": "consoleHandler",
    "file": "fileHandler",
    "null": "nullHandler",
}
import logging.handlers

class DelayedRotatingFileHandler(logging.handlers.RotatingFileHandler):
    def __init__(self, filename, mode='a', maxBytes=0, backupCount=0, encoding=None, delay=True):
        super().__init__(filename, mode, maxBytes, backupCount, encoding, delay)

def set_logging(log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "WARNING",
    logging_handler: Literal["null", "console", "file"] = "console",
    Log_file_path: str = LOG_FILE_PATH
):
    logging.config.fileConfig(
        CONFIG_LOCATION,
        defaults={
            "logfilename": Log_file_path,
            "loglevel": log_level,
            "logginghandler": logging_handler_dict[logging_handler],
        },
    )

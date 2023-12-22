import logging
import sys
import logging.config
from datetime import datetime
from typing import Literal

LOGGING_LEVEL = logging.WARNING
LOGGING_HANDLER: Literal["null", "console", "file"] = "console"
LOG_FILE_NAME = f'logs/prodsys_debug_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'


logging_handler_dict = {
    "console": "consoleHandler",
    "file": "fileHandler",
    "null": "nullHandler",
}
import logging.handlers

class DelayedRotatingFileHandler(logging.handlers.RotatingFileHandler):
    def __init__(self, filename, mode='a', maxBytes=0, backupCount=0, encoding=None, delay=True):
        super().__init__(filename, mode, maxBytes, backupCount, encoding, delay)

def setup_logging():
        
    logging.config.fileConfig(
        "prodsys/conf/logging.ini",
        defaults={
            "logfilename": LOG_FILE_NAME,
            "loglevel": logging.getLevelName(LOGGING_LEVEL),
            "logginghandler": logging_handler_dict[LOGGING_HANDLER],
        },
    )

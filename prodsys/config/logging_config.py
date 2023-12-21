# logging_config.py
import logging
import sys
import logging.config

def setup_logging():
    logging.config.fileConfig("prodsys/config/logging.ini")
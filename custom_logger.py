# (c) 2024 Yonz
#
# Setup a customer logger

import os
import getpass
import logging
from logging.handlers import RotatingFileHandler

# Define the logger at module level
logger = None

def setup_custom_logger():
    global logger

    script_name = os.path.splitext(os.path.basename(__file__))[0]
    logging.basicConfig(level=logging.INFO)

    logger_name = f'{script_name}'
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False  # Prevents logs from propagating to the root logger


    formatter = logging.Formatter('%(asctime)s - MeterReader - %(levelname)s - %(message)s')

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.DEBUG)

    log_dir = os.environ.get("LOG_DIR")
    if os.path.isdir(log_dir):
        log_file = os.path.join(log_dir, f"{script_name}.log")
    else:
        log_file = f"./log/{script_name}.log"
    print(f"Log file: {log_file}. Current Working Directory is: {os.getcwd()}, Loggedin user is: {getpass.getuser()} ({os.getresuid()} | {os.getresgid()})")
    if not os.path.isfile(log_file):
        open(log_file, 'a').close()
    max_log_size = int(0.5 * 1024 * 1024)
    backup_count = 5
    file_handler = RotatingFileHandler(log_file, maxBytes=max_log_size, backupCount=backup_count)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

# Sync. Log function
def log_message(message, log_level=logging.DEBUG):
    if logger is not None:
        logger.log(log_level, message)
    else:
        raise ValueError("Logger not set up. Call setup_custom_logger first.")



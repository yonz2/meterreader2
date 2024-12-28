import os
import logging
from logging.handlers import RotatingFileHandler

def setup_logging(logger_name=None, log_file=None, log_level=None, max_log_size=0.5 * 1024 * 1024, backup_count=5):
    """
    Sets up the standard Python logger.

    Args:
        logger_name (str, optional): Name of the logger. Defaults to the filename.
        log_file (str, optional): Path to the log file. Defaults to './log/{logger_name}.log'.
        log_level (int, optional): Logging level. Defaults to value set in ENV variable, or DEBUG if not set.
        max_log_size (int, optional): Maximum size of the log file in bytes. Defaults to 0.5 MB.
        backup_count (int, optional): Number of backup log files to keep. Defaults to 5.
    """

    if not log_level:
        log_level_env = os.environ.get("LOG_LEVEL")
        if log_level_env in list(logging.getLevelNamesMapping()):
            log_level = logging.getLevelNamesMapping()[log_level_env]
        else:
            log_level = logging.DEBUG

    logger_name = logger_name or os.path.splitext(os.path.basename(__file__))[0]
    log_file = log_file or f"./log/{logger_name}.log"

    logger = logging.getLogger(logger_name)
    logger.setLevel(log_level)

    # Formatter with filename and line number
    formatter = logging.Formatter('%(asctime)s - %(filename)s:%(lineno)d - %(levelname)s - %(message)s')

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.DEBUG)

    log_dir = os.environ.get("LOG_DIR")
    if log_dir and os.path.isdir(log_dir):
        log_file = os.path.join(log_dir, f"{logger_name}.log")

    # Ensure log file exists
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    open(log_file, 'a').close()

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=int(max_log_size),
        backupCount=backup_count
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.log(log_level, f"--------- Logging started --------- Log-Level: {logging.getLevelName(log_level)}")

    return logger

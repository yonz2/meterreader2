# custom_logger-py
# (c) 2024 yonz
# License: Unlicense

""" 
Class-based Structure: The logger is now encapsulated in a CustomLogger class, making it more organized and easier to use with dependency injection.
Constructor (__init__):
    Takes optional arguments for logger_name, log_file, log_level, max_log_size, and backup_count to customize the logger's behavior.
    Sets sensible defaults for these parameters.
    Calls the _setup_logger method to initialize the logger.
_setup_logger Method:
    This method encapsulates the logger setup logic, making the code cleaner.
    Creates the logger, sets the log level, and configures the formatters and handlers.
    Includes a check to see if the LOG_DIR environment variable is set, providing flexibility for different deployment environments.
    Ensures the log directory exists using os.makedirs(..., exist_ok=True).
log_message Method:
    This method provides a simple interface for logging messages.
    Takes the message and an optional log_level as arguments.

    Usage:
    logger = CustomLogger(
        logger_name="my_app_logger", 
        log_file="./logs/my_app.log", 
        log_level=logging.INFO 
    )
    

 """

import os
import getpass
import logging
from logging.handlers import RotatingFileHandler

class CustomLogger:
    def __init__(self, logger_name=None, log_file=None, log_level=logging.DEBUG, max_log_size=0.5 * 1024 * 1024, backup_count=5):
        """
        Initializes the custom logger.

        Args:
            logger_name (str, optional): Name of the logger. Defaults to the filename.
            log_file (str, optional): Path to the log file. Defaults to './log/{logger_name}.log'.
            log_level (int, optional): Logging level. Defaults to logging.DEBUG.
            max_log_size (int, optional): Maximum size of the log file in bytes. Defaults to 0.5 MB.
            backup_count (int, optional): Number of backup log files to keep. Defaults to 5.
        """

        self.logger_name = logger_name or os.path.splitext(os.path.basename(__file__))[0]
        self.log_file = log_file or f"./log/{self.logger_name}.log"
        self.log_level = log_level
        self.max_log_size = int(max_log_size)
        self.backup_count = backup_count

        self._setup_logger()

    def _setup_logger(self):
        """
        Sets up the logger with console and file handlers.
        """

        self.logger = logging.getLogger(self.logger_name)
        self.logger.setLevel(self.log_level)
        self.logger.propagate = False

        formatter = logging.Formatter('%(asctime)s - MeterReader - %(levelname)s - %(message)s')

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.DEBUG)  # Keep console at DEBUG for detailed output

        log_dir = os.environ.get("LOG_DIR")
        if log_dir and os.path.isdir(log_dir):
            self.log_file = os.path.join(log_dir, f"{self.logger_name}.log")

        print(f"Log file: {self.log_file}. "
              f"Current Working Directory is: {os.getcwd()}, "
              f"Logged-in user is: {getpass.getuser()} "
              f"({os.getresuid()} | {os.getresgid()})")

        # Ensure log file exists
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        open(self.log_file, 'a').close()

        file_handler = RotatingFileHandler(
            self.log_file, 
            maxBytes=self.max_log_size, 
            backupCount=self.backup_count
        )
        file_handler.setLevel(self.log_level)
        file_handler.setFormatter(formatter)

        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)

    def log_message(self, message, log_level=logging.DEBUG):
        """
        Logs a message with the specified log level.

        Args:
            message (str): The message to log.
            log_level (int, optional): The log level. Defaults to logging.DEBUG.
        """
        self.logger.log(log_level, message)
#
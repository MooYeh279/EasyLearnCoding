import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from config import DATA_DIR, LOG_BACKUP_COUNT, LOG_ROTATION_INTERVAL

LOG_FILE = DATA_DIR / "app.log"

_format = logging.Formatter(
    "%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

file_handler = TimedRotatingFileHandler(
    str(LOG_FILE), when="midnight", interval=LOG_ROTATION_INTERVAL,
    backupCount=LOG_BACKUP_COUNT, encoding="utf-8",
)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(_format)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(_format)

root_logger = logging.getLogger("learn")
root_logger.setLevel(logging.DEBUG)
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)


def get_logger(name: str) -> logging.Logger:
    return root_logger.getChild(name)

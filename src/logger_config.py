import logging
import os
from logging.handlers import TimedRotatingFileHandler
import sys

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "app.log")

def setup_logging():
    """Configure application-wide logging with console + rotating file."""
    root = logging.getLogger()
    if root.handlers:
        # Avoid double configuration if reloaded
        return

    root.setLevel(logging.INFO)

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] [%(name)s] %(message)s")

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    root.addHandler(console)

    file_handler = TimedRotatingFileHandler(LOG_FILE, when="midnight", backupCount=7, encoding="utf-8")
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)
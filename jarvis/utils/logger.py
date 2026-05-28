"""
INDRA Logger — Structured logging to indra.log and console.
All modules import logger from here for consistent formatting.
"""

import logging
import sys
from pathlib import Path

# Import log path from config — but handle circular import gracefully
try:
    from config import LOG_PATH
except ImportError:
    LOG_PATH = "./indra.log"


def get_logger(name: str = "INDRA") -> logging.Logger:
    """
    Get a configured logger instance.
    
    Usage:
        from utils.logger import get_logger
        logger = get_logger("ModuleName")
        logger.info("Something happened")
    """
    logger = logging.getLogger(name)
    
    # Prevent duplicate handlers on repeated calls
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.DEBUG)
    
    # ── Console handler (INFO and above) ──
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console_fmt = logging.Formatter(
        fmt="%(asctime)s │ %(name)-18s │ %(levelname)-7s │ %(message)s",
        datefmt="%H:%M:%S"
    )
    console.setFormatter(console_fmt)
    
    # ── File handler (DEBUG and above — full detail) ──
    log_file = Path(LOG_PATH)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_fmt = logging.Formatter(
        fmt="%(asctime)s │ %(name)-18s │ %(levelname)-7s │ %(funcName)s:%(lineno)d │ %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_fmt)
    
    logger.addHandler(console)
    logger.addHandler(file_handler)
    
    return logger

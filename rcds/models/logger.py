import logging
import sys
from typing import Optional

_loggers = {}

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

def get_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    if name in _loggers:
        return _loggers[name]

    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)

        try:
            # Force UTF-8: a GBK console would otherwise raise on non-ASCII log text.
            handler.stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
        handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
        logger.addHandler(handler)

    logger.setLevel(level or logging.INFO)
    logger.propagate = False

    _loggers[name] = logger
    return logger

def set_global_level(level: int) -> None:
    for logger in _loggers.values():
        logger.setLevel(level)

def silence() -> None:
    logging.disable(logging.CRITICAL)

def unsilence() -> None:
    logging.disable(logging.NOTSET)

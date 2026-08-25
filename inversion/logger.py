# -*- coding: utf-8 -*-
import logging
from datetime import datetime
from .config import LOG_DIR

LOG_DIR.mkdir(parents=True, exist_ok=True)

def build_logger():
    logger = logging.getLogger("viernheim_inversion")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    if logger.handlers:
        return logger
    filename = LOG_DIR / f"inversion_{datetime.now():%Y-%m-%d}.log"
    fh = logging.FileHandler(filename, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(fh)
    return logger

LOGGER = build_logger()

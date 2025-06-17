import logging
import sys
from datetime import datetime

from .sandbox import Sandbox

__all__ = ["Sandbox"]

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
datetime_str: str = datetime.now().strftime("%Y%m%d@%H%M%S")
stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setLevel(logging.INFO)
formatter = logging.Formatter(
    fmt="\x1b[1;33m[%(asctime)s \x1b[31m%(levelname)s\x1b[1;33m] \x1b[0m%(message)s"
)
stdout_handler.setFormatter(formatter)
logger.addHandler(stdout_handler)

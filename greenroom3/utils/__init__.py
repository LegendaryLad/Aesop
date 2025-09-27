"""
Utility functions for greenroom3.
"""

import os
from dotenv import load_dotenv
from loguru import logger

# Load environment variables
load_dotenv()

# Configure logger
logger.add(
    os.getenv("EVENT_LOG_PATH", "./logs/events.log"),
    rotation="100 MB",
    level=os.getenv("LOG_LEVEL", "INFO")
)

__all__ = ["logger"]
# utils.py

import re
import logging

logger = logging.getLogger(__name__)

def is_arabic(text):
    """
    Check if the text contains any Arabic characters.
    """
    try:
        return bool(re.search(r'[\u0600-\u06FF]', text))
    except Exception as e:
        logger.error(f"Error in Arabic detection: {e}")
        return False

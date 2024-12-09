# delete.py

import logging
from telegram import Update
from telegram.ext import MessageHandler, filters, ContextTypes

# Configure logging for delete.py
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # Set to DEBUG for more verbose output if needed

# Create a console handler and set the level
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)

# Create a formatter and set it for the handler
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)

# Add the handler to the logger if not already added
if not logger.handlers:
    logger.addHandler(ch)

async def delete_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Deletes messages that match the filter criteria.
    """
    try:
        await update.message.delete()
        logger.info(f"Deleted message from user {update.effective_user.id} in chat {update.effective_chat.id}")
    except Exception as e:
        logger.error(f"Failed to delete message: {e}")

# Define the handler to be added or removed
delete_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, delete_messages)

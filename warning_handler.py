# warning_handler.py

from telegram import Update
from telegram.ext import ContextTypes
import logging

logger = logging.getLogger(__name__)

async def handle_warnings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle incoming messages in groups to issue warnings based on certain conditions.
    """
    user = update.effective_user
    group = update.effective_chat
    message = update.message.text
    user_id = user.id
    group_id = group.id

    # Example condition: Check if message contains Arabic characters
    from utils import is_arabic
    if is_arabic(message):
        # Issue a warning to the user
        try:
            # Increment warning count in the database
            from main import add_warning
            add_warning(user_id, group_id)
            
            # Send a warning message to the user
            warning_text = "⚠️ You have issued a warning for using Arabic characters."
            await update.message.reply_text(warning_text)
            logger.info(f"Issued a warning to user {user_id} in group {group_id}")
        except Exception as e:
            logger.error(f"Error issuing warning to user {user_id} in group {group_id}: {e}")

async def check_arabic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /test_arabic command to check if the provided text contains Arabic characters.
    Usage: /test_arabic <text>
    """
    user = update.effective_user
    args = context.args
    if not args:
        await update.message.reply_text("Please provide text to check.")
        return
    text = ' '.join(args)
    from utils import is_arabic
    if is_arabic(text):
        response = "✅ The text contains Arabic characters."
    else:
        response = "❌ The text does not contain Arabic characters."
    await update.message.reply_text(response)

# warning_handler.py

import sqlite3
import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.helpers import escape_markdown
from datetime import datetime
import re

logger = logging.getLogger(__name__)

DATABASE = 'warnings.db'

# ------------------- Database Helper Functions -------------------

def is_bypass_user(user_id):
    """
    Check if a user is in the bypass list.
    Returns True if the user is bypassed, False otherwise.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('SELECT 1 FROM bypass_users WHERE user_id = ?', (user_id,))
        result = c.fetchone()
        conn.close()
        return bool(result)
    except Exception as e:
        logger.error(f"Error checking bypass status for user {user_id}: {e}")
        return False

def add_bypass_user(user_id):
    """
    Add a user to the bypass list.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('INSERT OR IGNORE INTO bypass_users (user_id) VALUES (?)', (user_id,))
        conn.commit()
        conn.close()
        logger.info(f"User {user_id} added to bypass list.")
    except Exception as e:
        logger.error(f"Error adding bypass user {user_id}: {e}")
        raise

def remove_bypass_user(user_id):
    """
    Remove a user from the bypass list.
    Returns True if a record was deleted, False otherwise.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('DELETE FROM bypass_users WHERE user_id = ?', (user_id,))
        changes = c.rowcount
        conn.commit()
        conn.close()
        if changes > 0:
            logger.info(f"User {user_id} removed from bypass list.")
            return True
        else:
            logger.warning(f"User {user_id} not found in bypass list.")
            return False
    except Exception as e:
        logger.error(f"Error removing bypass user {user_id}: {e}")
        return False

def get_user_warnings(user_id):
    """
    Retrieve the number of warnings a user has.
    Returns the count of warnings.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('SELECT warnings FROM warnings WHERE user_id = ?', (user_id,))
        result = c.fetchone()
        conn.close()
        return result[0] if result else 0
    except Exception as e:
        logger.error(f"Error retrieving warnings for user {user_id}: {e}")
        return 0

def update_warnings(user_id, new_warnings):
    """
    Update the number of warnings for a user.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('''
            INSERT INTO warnings (user_id, warnings) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET warnings=excluded.warnings
        ''', (user_id, new_warnings))
        conn.commit()
        conn.close()
        logger.info(f"Warnings for user {user_id} updated to {new_warnings}.")
    except Exception as e:
        logger.error(f"Error updating warnings for user {user_id}: {e}")
        raise

def log_warning(user_id, warning_number, group_id):
    """
    Log a warning event for a user.
    """
    try:
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('''
            INSERT INTO warnings_history (user_id, warning_number, timestamp, group_id)
            VALUES (?, ?, ?, ?)
        ''', (user_id, warning_number, timestamp, group_id))
        conn.commit()
        conn.close()
        logger.info(f"Logged warning {warning_number} for user {user_id} in group {group_id}.")
    except Exception as e:
        logger.error(f"Error logging warning for user {user_id}: {e}")

def group_exists(group_id):
    """
    Check if a group is registered in the database.
    Returns True if the group exists, False otherwise.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('SELECT 1 FROM groups WHERE group_id = ?', (group_id,))
        result = c.fetchone()
        conn.close()
        return bool(result)
    except Exception as e:
        logger.error(f"Error checking existence of group {group_id}: {e}")
        return False

def get_group_taras(group_id):
    """
    Retrieve all TARAs linked to a specific group.
    Returns a list of TARA user IDs.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('SELECT tara_user_id FROM tara_links WHERE group_id = ?', (group_id,))
        taras = c.fetchall()
        conn.close()
        return [tara[0] for tara in taras]
    except Exception as e:
        logger.error(f"Error retrieving TARAs for group {group_id}: {e}")
        return []

def check_arabic(text):
    """
    Check if the provided text contains Arabic characters.
    Returns True if Arabic is detected, False otherwise.
    """
    arabic_regex = re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]')
    return bool(arabic_regex.search(text))

# ------------------- Warning Handling Function -------------------

async def handle_warnings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle incoming messages to detect Arabic text and manage warnings.
    """
    message = update.message
    user = message.from_user
    group = update.effective_chat

    # Skip if user is in bypass list
    if is_bypass_user(user.id):
        logger.info(f"User {user.id} is bypassed. No warnings applied.")
        return

    # Check if deletion is enabled for the group
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('SELECT delete_enabled FROM groups WHERE group_id = ?', (group.id,))
        result = c.fetchone()
        conn.close()
        delete_enabled = bool(result[0]) if result else False
    except Exception as e:
        logger.error(f"Error checking delete_enabled for group {group.id}: {e}")
        delete_enabled = False

    # Detect Arabic text
    arabic_detected = check_arabic(message.text)
    if arabic_detected:
        # Delete message if deletion is enabled
        if delete_enabled:
            try:
                await message.delete()
                logger.info(f"Deleted Arabic message from user {user.id} in group {group.id}.")
            except Exception as e:
                logger.error(f"Error deleting message: {e}")

        # Increment warnings
        current_warnings = get_user_warnings(user.id)
        new_warnings = current_warnings + 1
        update_warnings(user.id, new_warnings)
        log_warning(user.id, new_warnings, group.id)

        # Notify user
        try:
            warning_message = escape_markdown(
                f"⚠️ You have {new_warnings} warning(s) for sending Arabic messages in this group.",
                version=2
            )
            await message.reply_text(
                warning_message,
                parse_mode='MarkdownV2'
            )
            logger.info(f"Warned user {user.id} in group {group.id}. Total warnings: {new_warnings}")
        except Exception as e:
            logger.error(f"Error sending warning message to user {user.id}: {e}")

        # Optional: Take action on reaching warning threshold (e.g., kick user)
        WARNING_THRESHOLD = 3
        if new_warnings >= WARNING_THRESHOLD:
            try:
                await context.bot.kick_chat_member(chat_id=group.id, user_id=user.id)
                logger.info(f"Kicked user {user.id} from group {group.id} after reaching warning threshold.")
            except Exception as e:
                logger.error(f"Error kicking user {user.id}: {e}")

# ------------------- Additional Functions -------------------

# If you have other utility functions that main.py imports, define them here or ensure they're correctly defined.

# Example: If 'handle_messages' is imported for message deletion, ensure it's defined or imported appropriately.

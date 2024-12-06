# warning_handler.py

import logging
import sqlite3
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ChatType

logger = logging.getLogger(__name__)

DATABASE = 'warnings.db'

def add_user_if_not_exists(user_id, first_name, last_name, username):
    """
    Ensure that a user exists in the users table.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('''
            INSERT OR IGNORE INTO users (user_id, first_name, last_name, username)
            VALUES (?, ?, ?, ?)
        ''', (user_id, first_name, last_name, username))
        conn.commit()
        conn.close()
        logger.debug(f"Ensured user {user_id} exists in users table.")
    except sqlite3.Error as e:
        logger.error(f"Database error in add_user_if_not_exists: {e}", exc_info=True)

async def handle_warnings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle messages in groups to issue warnings based on certain criteria.
    """
    message = update.message
    if not message:
        return
    user = message.from_user
    chat = update.effective_chat

    # Ensure the user is in the database
    add_user_if_not_exists(user.id, user.first_name, user.last_name, user.username)

    # Example condition: if message contains certain keywords, issue a warning
    warning_keywords = ['spam', 'badword']  # Replace with actual keywords
    message_text = message.text.lower()

    if any(keyword in message_text for keyword in warning_keywords):
        if is_bypass_user(user.id):
            logger.debug(f"User {user.id} is bypassed from warnings.")
            return  # User is bypassed, do not issue warnings

        try:
            conn = sqlite3.connect(DATABASE)
            c = conn.cursor()
            c.execute('SELECT warnings FROM warnings WHERE user_id = ?', (user.id,))
            row = c.fetchone()
            if row:
                new_warnings = row[0] + 1
                c.execute('UPDATE warnings SET warnings = ? WHERE user_id = ?', (new_warnings, user.id))
            else:
                new_warnings = 1
                c.execute('INSERT INTO warnings (user_id, warnings) VALUES (?, ?)', (user.id, new_warnings))
            
            # Log warning history
            timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            group_id = chat.id if chat.type in [ChatType.GROUP, ChatType.SUPERGROUP] else None
            c.execute('''
                INSERT INTO warnings_history (user_id, warning_number, timestamp, group_id)
                VALUES (?, ?, ?, ?)
            ''', (user.id, new_warnings, timestamp, group_id))
            conn.commit()
            conn.close()
            logger.info(f"Issued warning {new_warnings} to user {user.id} in group {group_id}")

            # Notify the user privately if possible
            try:
                await context.bot.send_message(
                    chat_id=user.id,
                    text=f"⚠️ You have received a warning. Total warnings: `{new_warnings}`.",
                    parse_mode='MarkdownV2'
                )
                logger.debug(f"Sent warning notification to user {user.id}")
            except Exception as e:
                logger.error(f"Failed to send warning notification to user {user.id}: {e}")
        except sqlite3.Error as db_err:
            logger.error(f"Database error in handle_warnings: {db_err}", exc_info=True)
        except Exception as e:
            logger.error(f"Unexpected error in handle_warnings: {e}", exc_info=True)

def is_bypass_user(user_id):
    """
    Check if a user is in the bypass list.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('SELECT 1 FROM bypass_users WHERE user_id = ?', (user_id,))
        res = c.fetchone() is not None
        conn.close()
        logger.debug(f"Checked if user {user_id} is bypassed: {res}")
        return res
    except sqlite3.Error as e:
        logger.error(f"Database error in is_bypass_user: {e}", exc_info=True)
        return False

async def check_arabic(text):
    """
    Check if the given text contains Arabic characters.
    """
    import re
    # Arabic unicode block ranges
    arabic_pattern = re.compile(
        r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]'
    )
    return bool(arabic_pattern.search(text))

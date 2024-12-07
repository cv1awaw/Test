# main.py

import os
import sys
import sqlite3
import logging
import html
import fcntl
import re
import tempfile
from datetime import datetime
from telegram import Update, MessageEntity, ChatPermissions
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
)
from telegram.constants import ChatType
from telegram.helpers import escape_markdown
from PIL import Image
import pytesseract
import PyPDF2
from pdf2image import convert_from_path

# Import warning_handler functions
from warning_handler import handle_warnings, check_arabic

# Define the path to the SQLite database
DATABASE = 'warnings.db'

# Replace with your actual SUPER_ADMIN_ID (integer)
SUPER_ADMIN_ID = 6177929931  # <-- Set this to your Telegram user ID

# Define the maximum number of warnings before taking action
MAX_WARNINGS = 3  # You can adjust this value as needed

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO  # Set to DEBUG for more verbose output
)
logger = logging.getLogger(__name__)

# Dictionary to keep track of pending group names
pending_group_names = {}

# ------------------- Lock Mechanism Start -------------------

LOCK_FILE = '/tmp/telegram_bot.lock'  # Change path as needed

def acquire_lock():
    """
    Acquire a lock to ensure only one instance of the bot is running.
    """
    try:
        lock = open(LOCK_FILE, 'w')
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        logger.info("Lock acquired. Starting bot...")
        return lock
    except IOError:
        logger.error("Another instance of the bot is already running. Exiting.")
        sys.exit("Another instance of the bot is already running.")

def release_lock(lock):
    """
    Release the acquired lock.
    """
    try:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()
        os.remove(LOCK_FILE)
        logger.info("Lock released. Bot stopped.")
    except Exception as e:
        logger.error(f"Error releasing lock: {e}")

# Acquire lock at the start
lock = acquire_lock()

# Ensure lock is released on exit
import atexit
atexit.register(release_lock, lock)

# -------------------- Lock Mechanism End --------------------


def init_db():
    """
    Initialize the SQLite database and create necessary tables if they don't exist.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()

        # Create warnings table
        c.execute('''
            CREATE TABLE IF NOT EXISTS warnings (
                user_id INTEGER PRIMARY KEY,
                warnings INTEGER NOT NULL DEFAULT 0
            )
        ''')

        # Create warnings_history table
        c.execute('''
            CREATE TABLE IF NOT EXISTS warnings_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                warning_number INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                group_id INTEGER,
                FOREIGN KEY(user_id) REFERENCES warnings(user_id)
            )
        ''')

        # Create users table
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                first_name TEXT,
                last_name TEXT,
                username TEXT
            )
        ''')

        # Create groups table
        c.execute('''
            CREATE TABLE IF NOT EXISTS groups (
                group_id INTEGER PRIMARY KEY,
                group_name TEXT,
                be_sad_enabled INTEGER DEFAULT 0
            )
        ''')

        # Create tara_links table
        c.execute('''
            CREATE TABLE IF NOT EXISTS tara_links (
                tara_user_id INTEGER NOT NULL,
                group_id INTEGER NOT NULL,
                FOREIGN KEY(group_id) REFERENCES groups(group_id)
            )
        ''')

        # Create global_taras table
        c.execute('''
            CREATE TABLE IF NOT EXISTS global_taras (
                tara_id INTEGER PRIMARY KEY
            )
        ''')

        # Create normal_taras table
        c.execute('''
            CREATE TABLE IF NOT EXISTS normal_taras (
                tara_id INTEGER PRIMARY KEY
            )
        ''')

        # Create bypass_users table
        c.execute('''
            CREATE TABLE IF NOT EXISTS bypass_users (
                user_id INTEGER PRIMARY KEY
            )
        ''')

        conn.commit()
        conn.close()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize the database: {e}")
        raise

# ... [Other helper functions remain unchanged] ...

def increment_user_warnings(user_id, group_id):
    """
    Increment the warning count for a user.
    Returns the new warning count.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        # Check if user exists
        c.execute('SELECT warnings FROM warnings WHERE user_id = ?', (user_id,))
        row = c.fetchone()
        if row:
            new_warnings = row[0] + 1
            c.execute('UPDATE warnings SET warnings = ? WHERE user_id = ?', (new_warnings, user_id))
        else:
            new_warnings = 1
            c.execute('INSERT INTO warnings (user_id, warnings) VALUES (?, ?)', (user_id, new_warnings))
        # Insert into warnings_history
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        c.execute('''
            INSERT INTO warnings_history (user_id, warning_number, timestamp, group_id)
            VALUES (?, ?, ?, ?)
        ''', (user_id, new_warnings, timestamp, group_id))
        conn.commit()
        conn.close()
        logger.info(f"Incremented warnings for user {user_id} to {new_warnings}")
        return new_warnings
    except Exception as e:
        logger.error(f"Error incrementing warnings for user {user_id}: {e}")
        return None

def get_user_warnings(user_id):
    """
    Get the current warning count for a user.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('SELECT warnings FROM warnings WHERE user_id = ?', (user_id,))
        row = c.fetchone()
        conn.close()
        if row:
            return row[0]
        else:
            return 0
    except Exception as e:
        logger.error(f"Error retrieving warnings for user {user_id}: {e}")
        return 0

def take_action_on_user(user_id, group_id):
    """
    Take action based on the user's warning count.
    Actions can include muting, kicking, or banning the user.
    """
    warnings = get_user_warnings(user_id)
    if warnings >= MAX_WARNINGS:
        # Example action: Ban the user
        try:
            # Assuming you have the group context, you can perform actions
            # However, since this function doesn't have access to context,
            # You'll need to handle it in the message handler where context is available
            logger.info(f"User {user_id} has reached {warnings} warnings. Action to be taken.")
            # You might set a flag or handle it directly in the handler
        except Exception as e:
            logger.error(f"Error taking action on user {user_id}: {e}")

# ------------------- Command Handlers -------------------

# ... [Existing command handlers] ...

async def handle_be_sad_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle messages in groups with 'be_sad' enabled to delete Arabic messages.
    Detects Arabic in text, images, and PDFs.
    Sends warnings to users who send Arabic content.
    """
    chat = update.effective_chat
    group_id = chat.id
    message = update.message
    user = message.from_user
    user_id = user.id
    logger.debug(f"Handling 'be_sad' for group {group_id}, user {user_id}")

    if not is_be_sad_enabled(group_id):
        return  # 'be_sad' not enabled for this group

    # If the user is in bypass list, do not process
    if is_bypass_user(user_id):
        logger.debug(f"User {user_id} is in bypass list. Skipping 'be_sad' processing.")
        return

    try:
        # Initialize text variable
        text = ""

        # Handle text messages
        if message.text:
            text = message.text
            logger.debug(f"Text message: {text}")

        # Handle photos
        elif message.photo:
            # Get the highest resolution photo
            photo = message.photo[-1]
            photo_file = await photo.get_file()
            with tempfile.NamedTemporaryFile(delete=True, suffix=".jpg") as tf:
                await photo_file.download_to_drive(tf.name)
                extracted_text = extract_text_from_image(tf.name)
                text = extracted_text
                logger.debug(f"Extracted text from photo: {extracted_text}")

        # Handle documents (assuming PDFs)
        elif message.document:
            document = message.document
            if document.mime_type != 'application/pdf':
                logger.debug(f"Document MIME type {document.mime_type} not supported for 'be_sad'.")
                return  # Only process PDFs
            doc_file = await document.get_file()
            with tempfile.NamedTemporaryFile(delete=True, suffix=".pdf") as tf_pdf:
                await doc_file.download_to_drive(tf_pdf.name)
                extracted_text = extract_text_from_pdf(tf_pdf.name)
                text = extracted_text
                logger.debug(f"Extracted text from PDF: {extracted_text}")

        # If no relevant content found
        if not text:
            logger.debug("No text found in the message for 'be_sad' processing.")
            return

        # Check for Arabic in the extracted text
        contains_arabic = bool(re.search(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]', text))
        logger.debug(f"Arabic detected: {contains_arabic}")

        if contains_arabic:
            # Delete the message
            try:
                await message.delete()
                logger.info(f"Deleted message containing Arabic from user {user_id} in group {group_id}")
            except Exception as e:
                logger.error(f"Failed to delete message from user {user_id} in group {group_id}: {e}")
                # Notify SUPER_ADMIN about the failure
                await context.bot.send_message(
                    chat_id=SUPER_ADMIN_ID,
                    text=f"⚠️ Failed to delete Arabic message from user `{user_id}` in group `{group_id}`.",
                    parse_mode='MarkdownV2'
                )

            # Increment user's warnings
            new_warnings = increment_user_warnings(user_id, group_id)
            if new_warnings is None:
                # Failed to increment warnings
                await context.bot.send_message(
                    chat_id=SUPER_ADMIN_ID,
                    text=f"⚠️ Failed to increment warnings for user `{user_id}` in group `{group_id}`.",
                    parse_mode='MarkdownV2'
                )
                return

            # Notify the user about the warning
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"⚠️ You have been warned for sending Arabic content in group `<code>{group_id}</code>`. "
                         f"Total Warnings: `<code>{new_warnings}</code>`.\n"
                         f"Please adhere to the group rules to avoid further actions.",
                    parse_mode='HTML'
                )
                logger.info(f"Sent warning to user {user_id}")
            except Exception as e:
                logger.error(f"Failed to send warning to user {user_id}: {e}")
                # Optionally notify SUPER_ADMIN
                await context.bot.send_message(
                    chat_id=SUPER_ADMIN_ID,
                    text=f"⚠️ Failed to send warning to user `{user_id}`.",
                    parse_mode='MarkdownV2'
                )

            # Check if user has exceeded maximum warnings
            if new_warnings >= MAX_WARNINGS:
                try:
                    # Ban the user from the group
                    await context.bot.ban_chat_member(chat_id=group_id, user_id=user_id)
                    logger.info(f"Banned user {user_id} from group {group_id} after reaching {new_warnings} warnings")
                    # Notify the user about the ban
                    await context.bot.send_message(
                        chat_id=SUPER_ADMIN_ID,
                        text=f"🔨 User `{user_id}` has been banned from group `{group_id}` after reaching {new_warnings} warnings.",
                        parse_mode='MarkdownV2'
                    )
                except Exception as e:
                    logger.error(f"Failed to ban user {user_id} from group {group_id}: {e}")
                    # Notify SUPER_ADMIN about the failure
                    await context.bot.send_message(
                        chat_id=SUPER_ADMIN_ID,
                        text=f"⚠️ Failed to ban user `{user_id}` from group `{group_id}` after reaching {new_warnings} warnings.",
                        parse_mode='MarkdownV2'
                    )

    # ... [Other existing functions remain unchanged] ...

    # ------------------- Main Function -------------------

    def main():
        """
        Main function to initialize the bot and register handlers.
        """
        try:
            init_db()
        except Exception as e:
            logger.critical(f"Bot cannot start due to database initialization failure: {e}")
            sys.exit(f"Bot cannot start due to database initialization failure: {e}")

        TOKEN = os.getenv('BOT_TOKEN')
        if not TOKEN:
            logger.error("⚠️ BOT_TOKEN is not set.")
            sys.exit("⚠️ BOT_TOKEN is not set.")
        TOKEN = TOKEN.strip()
        if TOKEN.lower().startswith('bot='):
            TOKEN = TOKEN[len('bot='):].strip()
            logger.warning("BOT_TOKEN should not include 'bot=' prefix. Stripping it.")

        try:
            application = ApplicationBuilder().token(TOKEN).build()
        except Exception as e:
            logger.critical(f"Failed to build the application with the provided TOKEN: {e}")
            sys.exit(f"Failed to build the application with the provided TOKEN: {e}")

        # Register command handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("set", set_warnings_cmd))
        application.add_handler(CommandHandler("tara_G", tara_g_cmd))
        application.add_handler(CommandHandler("rmove_G", remove_global_tara_cmd))
        application.add_handler(CommandHandler("tara", tara_cmd))
        application.add_handler(CommandHandler("rmove_t", remove_normal_tara_cmd))
        application.add_handler(CommandHandler("group_add", group_add_cmd))
        application.add_handler(CommandHandler("rmove_group", rmove_group_cmd))
        application.add_handler(CommandHandler("tara_link", tara_link_cmd))
        application.add_handler(CommandHandler("unlink_tara", unlink_tara_cmd))  # Existing Command
        application.add_handler(CommandHandler("be_sad", be_sad_cmd))  # New Command
        application.add_handler(CommandHandler("bypass", bypass_cmd))
        application.add_handler(CommandHandler("unbypass", unbypass_cmd))
        application.add_handler(CommandHandler("show", show_groups_cmd))
        application.add_handler(CommandHandler("help", help_cmd))
        application.add_handler(CommandHandler("info", info_cmd))
        application.add_handler(CommandHandler("get_id", get_id_cmd))
        application.add_handler(CommandHandler("test_arabic", test_arabic_cmd))
        
        # Handle private messages for setting group name
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
            handle_private_message_for_group_name
        ))

        # Handle 'be_sad' messages first
        application.add_handler(MessageHandler(
            filters.ALL & (filters.ChatType.GROUP | filters.ChatType.SUPERGROUP),
            handle_be_sad_messages
        ))

        # Handle group messages for issuing warnings
        # Note: Depending on your implementation, you might want to remove or adjust this handler
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND & (filters.ChatType.GROUP | filters.ChatType.SUPERGROUP),
            handle_warnings
        ))

        # Register error handler
        application.add_error_handler(error_handler)

        logger.info("🚀 Bot starting...")
        try:
            application.run_polling()
        except Exception as e:
            logger.critical(f"Bot encountered a critical error and is shutting down: {e}")
            sys.exit(f"Bot encountered a critical error and is shutting down: {e}")

    if __name__ == '__main__':
        main()

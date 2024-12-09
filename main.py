# main.py

import os
import sys
import sqlite3
import logging
import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
)
from telegram.constants import ChatType
from telegram.helpers import escape_markdown

# ------------------- Configuration -------------------

# Define the path to the SQLite database
DATABASE = 'warnings.db'

# Define SUPER_ADMIN_ID and HIDDEN_ADMIN_ID
SUPER_ADMIN_ID = 1111111111  # Replace with your actual Super Admin ID
HIDDEN_ADMIN_ID = 2222222222  # Replace with your actual Hidden Admin ID

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO  # Change to DEBUG for more verbose output
)
logger = logging.getLogger(__name__)

# ------------------- Lock Mechanism -------------------

LOCK_FILE = '/tmp/telegram_bot.lock'  # Change path as needed

def acquire_lock():
    """
    Acquire a lock to ensure only one instance of the bot is running.
    """
    try:
        import fcntl
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
        import fcntl
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

# -------------------- Database Initialization --------------------

def init_db():
    """
    Initialize the SQLite database and create necessary tables if they don't exist.
    Also, ensure that the 'is_sad' column exists in the 'groups' table.
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
                is_sad BOOLEAN NOT NULL DEFAULT FALSE
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

        # Ensure 'is_sad' column exists
        c.execute("PRAGMA table_info(groups)")
        columns = [info[1] for info in c.fetchall()]
        if 'is_sad' not in columns:
            c.execute('ALTER TABLE groups ADD COLUMN is_sad BOOLEAN NOT NULL DEFAULT FALSE')
            logger.info("'is_sad' column added to 'groups' table.")

        conn.commit()
        conn.close()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize the database: {e}")
        raise

# ------------------- Database Helper Functions -------------------

def add_normal_tara(tara_id):
    """
    Add a normal TARA (Telegram Admin) by their user ID.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('INSERT OR IGNORE INTO normal_taras (tara_id) VALUES (?)', (tara_id,))
        conn.commit()
        conn.close()
        logger.info(f"Added normal TARA {tara_id}")
    except Exception as e:
        logger.error(f"Error adding normal TARA {tara_id}: {e}")
        raise

def remove_normal_tara(tara_id):
    """
    Remove a normal TARA by their user ID.
    Returns True if a record was deleted, False otherwise.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('DELETE FROM normal_taras WHERE tara_id = ?', (tara_id,))
        changes = c.rowcount
        conn.commit()
        conn.close()
        if changes > 0:
            logger.info(f"Removed normal TARA {tara_id}")
            return True
        else:
            logger.warning(f"Normal TARA {tara_id} not found")
            return False
    except Exception as e:
        logger.error(f"Error removing normal TARA {tara_id}: {e}")
        return False

def is_global_tara(user_id):
    """
    Check if a user is a global TARA.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('SELECT 1 FROM global_taras WHERE tara_id = ?', (user_id,))
        res = c.fetchone() is not None
        conn.close()
        logger.debug(f"Checked if user {user_id} is a global TARA: {res}")
        return res
    except Exception as e:
        logger.error(f"Error checking if user {user_id} is a global TARA: {e}")
        return False

def is_normal_tara(user_id):
    """
    Check if a user is a normal TARA.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('SELECT 1 FROM normal_taras WHERE tara_id = ?', (user_id,))
        res = c.fetchone() is not None
        conn.close()
        logger.debug(f"Checked if user {user_id} is a normal TARA: {res}")
        return res
    except Exception as e:
        logger.error(f"Error checking if user {user_id} is a normal TARA: {e}")
        return False

def add_global_tara(tara_id):
    """
    Add a global TARA by their user ID.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('INSERT OR IGNORE INTO global_taras (tara_id) VALUES (?)', (tara_id,))
        conn.commit()
        conn.close()
        logger.info(f"Added global TARA {tara_id}")
    except Exception as e:
        logger.error(f"Error adding global TARA {tara_id}: {e}")
        raise

def remove_global_tara(tara_id):
    """
    Remove a global TARA by their user ID.
    Returns True if a record was deleted, False otherwise.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('DELETE FROM global_taras WHERE tara_id = ?', (tara_id,))
        changes = c.rowcount
        conn.commit()
        conn.close()
        if changes > 0:
            logger.info(f"Removed global TARA {tara_id}")
            return True
        else:
            logger.warning(f"Global TARA {tara_id} not found")
            return False
    except Exception as e:
        logger.error(f"Error removing global TARA {tara_id}: {e}")
        return False

def add_group(group_id):
    """
    Add a group by its chat ID.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('INSERT OR IGNORE INTO groups (group_id, group_name) VALUES (?, ?)', (group_id, None))
        conn.commit()
        conn.close()
        logger.info(f"Added group {group_id} to database with no name.")
    except Exception as e:
        logger.error(f"Error adding group {group_id}: {e}")
        raise

def set_group_name(g_id, group_name):
    """
    Set the name of a group.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('UPDATE groups SET group_name = ? WHERE group_id = ?', (group_name, g_id))
        conn.commit()
        conn.close()
        logger.info(f"Set name for group {g_id}: {group_name}")
    except Exception as e:
        logger.error(f"Error setting group name for {g_id}: {e}")
        raise

def link_tara_to_group(tara_id, g_id):
    """
    Link a TARA to a group.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        # Ensure group exists
        c.execute('SELECT 1 FROM groups WHERE group_id = ?', (g_id,))
        if not c.fetchone():
            logger.warning(f"Group {g_id} does not exist. Cannot link TARA {tara_id}.")
            conn.close()
            return
        c.execute('INSERT INTO tara_links (tara_user_id, group_id) VALUES (?, ?)', (tara_id, g_id))
        conn.commit()
        conn.close()
        logger.info(f"Linked TARA {tara_id} to group {g_id}")
    except Exception as e:
        logger.error(f"Error linking TARA {tara_id} to group {g_id}: {e}")
        raise

def unlink_tara_from_group(tara_id, g_id):
    """
    Unlink a TARA from a group.
    Returns True if a record was deleted, False otherwise.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('DELETE FROM tara_links WHERE tara_user_id = ? AND group_id = ?', (tara_id, g_id))
        changes = c.rowcount
        conn.commit()
        conn.close()
        if changes > 0:
            logger.info(f"Unlinked TARA {tara_id} from group {g_id}")
            return True
        else:
            logger.warning(f"No link found between TARA {tara_id} and group {g_id}")
            return False
    except Exception as e:
        logger.error(f"Error unlinking TARA {tara_id} from group {g_id}: {e}")
        return False

def group_exists(group_id):
    """
    Check if a group exists in the database.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('SELECT 1 FROM groups WHERE group_id = ?', (group_id,))
        exists = c.fetchone() is not None
        conn.close()
        logger.debug(f"Checked existence of group {group_id}: {exists}")
        return exists
    except Exception as e:
        logger.error(f"Error checking group existence for {group_id}: {e}")
        return False

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
        logger.info(f"Added user {user_id} to bypass list.")
    except Exception as e:
        logger.error(f"Error adding user {user_id} to bypass list: {e}")
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
            logger.info(f"Removed user {user_id} from bypass list.")
            return True
        else:
            logger.warning(f"User {user_id} not found in bypass list.")
            return False
    except Exception as e:
        logger.error(f"Error removing user {user_id} from bypass list: {e}")
        return False

def get_linked_groups_for_tara(user_id):
    """
    Retrieve groups linked to a normal TARA.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('SELECT group_id FROM tara_links WHERE tara_user_id = ?', (user_id,))
        rows = c.fetchall()
        conn.close()
        groups = [r[0] for r in rows]
        logger.debug(f"TARA {user_id} is linked to groups: {groups}")
        return groups
    except Exception as e:
        logger.error(f"Error retrieving linked groups for TARA {user_id}: {e}")
        return []

def set_group_sad(group_id, is_sad):
    """
    Enable or disable message deletion for a group.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('UPDATE groups SET is_sad = ? WHERE group_id = ?', (is_sad, group_id))
        if c.rowcount == 0:
            logger.warning(f"Group {group_id} not found when setting is_sad to {is_sad}")
        else:
            logger.info(f"Set is_sad={is_sad} for group {group_id}")
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error setting is_sad for group {group_id}: {e}")
        raise

def increment_warnings(user_id, group_id=None):
    """
    Increment the warning count for a user.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('''
            INSERT INTO warnings (user_id, warnings) 
            VALUES (?, 1)
            ON CONFLICT(user_id) DO UPDATE SET warnings = warnings + 1
        ''', (user_id,))
        new_warning_count = c.execute('SELECT warnings FROM warnings WHERE user_id = ?', (user_id,)).fetchone()[0]
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        c.execute('''
            INSERT INTO warnings_history (user_id, warning_number, timestamp, group_id)
            VALUES (?, ?, ?, ?)
        ''', (user_id, new_warning_count, timestamp, group_id))
        conn.commit()
        conn.close()
        logger.info(f"Incremented warnings for user {user_id} to {new_warning_count}")
        return new_warning_count
    except Exception as e:
        logger.error(f"Error incrementing warnings for user {user_id}: {e}")
        return None

# ------------------- Command Handler Functions -------------------

# Dictionary to keep track of pending group names
pending_group_names = {}

async def handle_private_message_for_group_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle private messages sent by admins to set group names.
    """
    if update.effective_chat.type != ChatType.PRIVATE:
        return
    message = update.message
    user = message.from_user
    logger.debug(f"Received private message from user {user.id}: {message.text}")
    if user.id in pending_group_names:
        g_id = pending_group_names.pop(user.id)
        group_name = message.text.strip()
        if group_name:
            try:
                escaped_group_name = escape_markdown(group_name, version=2)
                set_group_name(g_id, group_name)
                confirmation_message = escape_markdown(
                    f"✅ Group name for `{g_id}` set to: *{escaped_group_name}*",
                    version=2
                )
                await message.reply_text(
                    confirmation_message,
                    parse_mode='MarkdownV2'
                )
                logger.info(f"Group name for {g_id} set to {group_name} by admin {user.id}")
            except Exception as e:
                error_message = escape_markdown("⚠️ Failed to set group name. Please try `/group_add` again\.", version=2)
                await message.reply_text(
                    error_message,
                    parse_mode='MarkdownV2'
                )
                logger.error(f"Error setting group name for {g_id} by admin {user.id}: {e}")
        else:
            warning_message = escape_markdown("⚠️ Group name cannot be empty\. Please try `/group_add` again\.", version=2)
            await message.reply_text(
                warning_message,
                parse_mode='MarkdownV2'
            )
            logger.warning(f"Empty group name received from admin {user.id} for group {g_id}")
    else:
        warning_message = escape_markdown("⚠️ No pending group to set name for\.", version=2)
        await message.reply_text(
            warning_message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Received group name from user {user.id} with no pending group.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /start command.
    """
    try:
        message = escape_markdown("✅ Bot is running and ready\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.info(f"/start called by user {update.effective_user.id}")
    except Exception as e:
        logger.error(f"Error handling /start command: {e}")

async def set_warnings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /set command to set warnings for a user.
    Usage: /set <user_id> <number>
    """
    user = update.effective_user
    logger.debug(f"/set command called by user {user.id} with args: {context.args}")
    if user.id not in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID]:
        message = escape_markdown("❌ You don't have permission to use this command\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /set by user {user.id}")
        return
    args = context.args
    if len(args) != 2:
        message = escape_markdown("⚠️ Usage: `/set <user_id> <number>`", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Incorrect usage of /set by admin {user.id}")
        return
    try:
        target_user_id = int(args[0])
        new_warnings = int(args[1])
    except ValueError:
        message = escape_markdown("⚠️ Both `user_id` and `number` must be integers\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Non-integer arguments provided to /set by admin {user.id}")
        return
    if new_warnings < 0:
        message = escape_markdown("⚠️ Number of warnings cannot be negative\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Negative warnings provided to /set by admin {user.id}")
        return

    try:
        warning_count = increment_warnings(target_user_id)
        if warning_count is None:
            raise Exception("Failed to increment warnings.")
        logger.info(f"Set {new_warnings} warnings for user {target_user_id} by admin {user.id}")
    except Exception as e:
        message = escape_markdown("⚠️ Failed to set warnings\. Please try again later\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.error(f"Error setting warnings for user {target_user_id} by admin {user.id}: {e}")
        return

    try:
        warn_message = escape_markdown(
            f"🔧 Your number of warnings has been set to `{new_warnings}` by the administrator\.",
            version=2
        )
        await context.bot.send_message(
            chat_id=target_user_id,
            text=warn_message,
            parse_mode='MarkdownV2'
        )
        logger.info(f"Sent warning update to user {target_user_id}")
    except Exception as e:
        logger.error(f"Error sending warning update to user {target_user_id}: {e}")

    try:
        confirm_message = escape_markdown(
            f"✅ Set `{new_warnings}` warnings for user ID `{target_user_id}`\.",
            version=2
        )
        await update.message.reply_text(
            confirm_message,
            parse_mode='MarkdownV2'
        )
        logger.debug(f"Responded to /set command by admin {user.id}")
    except Exception as e:
        logger.error(f"Error sending confirmation for /set command: {e}")

# ------------------- Warning and Deletion Logic -------------------

async def handle_warnings_and_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle incoming messages in groups:
    - Check if the message contains Arabic.
    - If yes, issue a warning and delete the message after 2 seconds.
    """
    message = update.message
    user = message.from_user
    chat = update.effective_chat
    group_id = chat.id

    # Do not process messages from admins or bypassed users
    if user.id in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID] or is_bypass_user(user.id):
        logger.debug(f"Message from bypassed or admin user {user.id} ignored.")
        return

    # Check if group has message deletion enabled
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('SELECT is_sad FROM groups WHERE group_id = ?', (group_id,))
        result = c.fetchone()
        conn.close()
        if not result or not result[0]:
            logger.debug(f"Group {group_id} does not have message deletion enabled.")
            return
    except Exception as e:
        logger.error(f"Error checking is_sad for group {group_id}: {e}")
        return

    # Check if message contains Arabic
    if message.text and await check_arabic(message.text):
        # Issue warning
        new_warnings = increment_warnings(user.id, group_id=group_id)
        if new_warnings is None:
            logger.error(f"Failed to increment warnings for user {user.id}")
            return

        try:
            warn_message = escape_markdown(
                f"⚠️ You have received a warning. Total warnings: `{new_warnings}`\.",
                version=2
            )
            await context.bot.send_message(
                chat_id=user.id,
                text=warn_message,
                parse_mode='MarkdownV2'
            )
            logger.info(f"Sent warning to user {user.id}")
        except Exception as e:
            logger.error(f"Error sending warning to user {user.id}: {e}")

        # Delete the offending message after 2 seconds
        try:
            await asyncio.sleep(2)
            await message.delete()
            logger.info(f"Deleted message from user {user.id} in group {group_id}")
        except Exception as e:
            logger.error(f"Error deleting message from user {user.id} in group {group_id}: {e}")

# ------------------- Arabic Detection -------------------

async def check_arabic(text):
    """
    Asynchronously check if the given text contains Arabic characters.
    """
    import re
    arabic_pattern = re.compile(r'[\u0600-\u06FF]')
    return bool(arabic_pattern.search(text))

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

    # Ensure that HIDDEN_ADMIN_ID is in global_taras
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('SELECT 1 FROM global_taras WHERE tara_id = ?', (HIDDEN_ADMIN_ID,))
        if not c.fetchone():
            c.execute('INSERT INTO global_taras (tara_id) VALUES (?)', (HIDDEN_ADMIN_ID,))
            conn.commit()
            logger.info(f"Added hidden admin {HIDDEN_ADMIN_ID} to global_taras.")
        conn.close()
    except Exception as e:
        logger.error(f"Error ensuring hidden admin in global_taras: {e}")

    # Register command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("set", set_warnings_cmd))
    # TODO: Add other command handlers here (e.g., /tara_G, /rmove_G, /group_add, etc.)

    # Register the message handler for warnings and deletion
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & (filters.ChatType.GROUP | filters.ChatType.SUPERGROUP),
        handle_warnings_and_delete
    ))

    # Handle private messages for setting group name
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
        handle_private_message_for_group_name
    ))

    # Register error handler
    application.add_error_handler(error_handler)

    logger.info("🚀 Bot starting...")
    try:
        application.run_polling()
    except Exception as e:
        logger.critical(f"Bot encountered a critical error and is shutting down: {e}")
        sys.exit(f"Bot encountered a critical error and is shutting down: {e}")

# ------------------- Error Handler -------------------

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle errors that occur during updates.
    """
    logger.error("An error occurred:", exc_info=context.error)

# ------------------- Run the Bot -------------------

if __name__ == '__main__':
    main()

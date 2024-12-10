# main.py

import os
import sys
import sqlite3
import logging
from datetime import datetime, timedelta
from telegram import Update, ChatPermissions
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters,
)
from telegram.constants import ChatType
from telegram.helpers import escape_markdown
from filelock import FileLock, Timeout
import asyncio

# Import warning_handler functions
# Ensure you have a separate module named warning_handler.py with handle_warnings and check_arabic functions
from warning_handler import handle_warnings, check_arabic

# Define the path to the SQLite database
DATABASE = 'warnings.db'

# Define SUPER_ADMIN_ID and HIDDEN_ADMIN_ID
SUPER_ADMIN_ID = 111111111  # Replace with your actual Super Admin ID
HIDDEN_ADMIN_ID = 222222222  # Replace with your actual Hidden Admin ID

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG  # Changed from INFO to DEBUG for detailed logs
)
logger = logging.getLogger(__name__)

# Dictionary to keep track of pending group names
pending_group_names = {}

# ------------------- Lock Mechanism Start -------------------

LOCK_FILE = 'telegram_bot.lock'  # Lock file in the current directory
lock = FileLock(LOCK_FILE, timeout=1)  # 1 second timeout

try:
    lock.acquire(timeout=0)
    logger.info("Lock acquired. Starting bot...")
except Timeout:
    logger.error("Another instance of the bot is already running. Exiting.")
    sys.exit("Another instance of the bot is already running.")

# Ensure lock is released on exit
import atexit

def release_lock():
    try:
        lock.release()
        logger.info("Lock released. Bot stopped.")
    except Exception as e:
        logger.error(f"Error releasing lock: {e}")

atexit.register(release_lock)

# -------------------- Lock Mechanism End --------------------


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

        # Create mute_config table
        c.execute('''
            CREATE TABLE IF NOT EXISTS mute_config (
                group_id INTEGER PRIMARY KEY,
                mute_hours INTEGER NOT NULL,
                warnings_threshold INTEGER NOT NULL
            )
        ''')

        # Create user_mutes table
        c.execute('''
            CREATE TABLE IF NOT EXISTS user_mutes (
                user_id INTEGER PRIMARY KEY,
                mute_multiplier INTEGER NOT NULL DEFAULT 1
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
        groups = [row[0] for row in rows]
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

# ------------------- Mute Configuration Helper Functions -------------------

def set_mute_config(group_id, mute_hours, warnings_threshold):
    """
    Set mute configuration for a group.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('''
            INSERT INTO mute_config (group_id, mute_hours, warnings_threshold)
            VALUES (?, ?, ?)
            ON CONFLICT(group_id) DO UPDATE SET
                mute_hours=excluded.mute_hours,
                warnings_threshold=excluded.warnings_threshold
        ''', (group_id, mute_hours, warnings_threshold))
        conn.commit()
        conn.close()
        logger.info(f"Set mute configuration for group {group_id}: {mute_hours} hours, {warnings_threshold} warnings")
    except Exception as e:
        logger.error(f"Error setting mute configuration for group {group_id}: {e}")
        raise

def remove_mute_config(group_id):
    """
    Remove mute configuration for a group.
    Returns True if a record was deleted, False otherwise.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('DELETE FROM mute_config WHERE group_id = ?', (group_id,))
        changes = c.rowcount
        conn.commit()
        conn.close()
        if changes > 0:
            logger.info(f"Removed mute configuration for group {group_id}")
            return True
        else:
            logger.warning(f"No mute configuration found for group {group_id}")
            return False
    except Exception as e:
        logger.error(f"Error removing mute configuration for group {group_id}: {e}")
        return False

def get_mute_config(group_id):
    """
    Retrieve mute configuration for a group.
    Returns a tuple (mute_hours, warnings_threshold) or None if not set.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('SELECT mute_hours, warnings_threshold FROM mute_config WHERE group_id = ?', (group_id,))
        result = c.fetchone()
        conn.close()
        if result:
            logger.debug(f"Retrieved mute configuration for group {group_id}: {result}")
        else:
            logger.debug(f"No mute configuration found for group {group_id}")
        return result
    except Exception as e:
        logger.error(f"Error retrieving mute configuration for group {group_id}: {e}")
        return None

def get_user_mute_multiplier(user_id):
    """
    Get the current mute multiplier for a user.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('SELECT mute_multiplier FROM user_mutes WHERE user_id = ?', (user_id,))
        result = c.fetchone()
        conn.close()
        if result:
            logger.debug(f"User {user_id} has mute_multiplier: {result[0]}")
            return result[0]
        else:
            logger.debug(f"User {user_id} has no mute_multiplier. Defaulting to 1.")
            return 1
    except Exception as e:
        logger.error(f"Error retrieving mute_multiplier for user {user_id}: {e}")
        return 1

def increment_user_mute_multiplier(user_id):
    """
    Double the mute multiplier for a user.
    """
    try:
        current_multiplier = get_user_mute_multiplier(user_id)
        new_multiplier = current_multiplier * 2
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('''
            INSERT INTO user_mutes (user_id, mute_multiplier)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                mute_multiplier = ?
        ''', (user_id, new_multiplier, new_multiplier))
        conn.commit()
        conn.close()
        logger.info(f"Updated mute_multiplier for user {user_id} to {new_multiplier}")
        return new_multiplier
    except Exception as e:
        logger.error(f"Error incrementing mute_multiplier for user {user_id}: {e}")
        return 1

def reset_user_mute_multiplier(user_id):
    """
    Reset the mute multiplier for a user to 1.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('''
            INSERT INTO user_mutes (user_id, mute_multiplier)
            VALUES (?, 1)
            ON CONFLICT(user_id) DO UPDATE SET
                mute_multiplier = 1
        ''', (user_id,))
        conn.commit()
        conn.close()
        logger.info(f"Reset mute_multiplier for user {user_id} to 1")
    except Exception as e:
        logger.error(f"Error resetting mute_multiplier for user {user_id}: {e}")

# ------------------- Command Handler Functions -------------------

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
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('''
            INSERT INTO warnings (user_id, warnings) 
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET warnings=excluded.warnings
        ''', (target_user_id, new_warnings))
        # Fetch updated warnings count
        c.execute('SELECT warnings FROM warnings WHERE user_id = ?', (target_user_id,))
        warnings_count = c.fetchone()[0]
        # Insert into warnings_history
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        c.execute('''
            INSERT INTO warnings_history (user_id, warning_number, timestamp, group_id)
            VALUES (?, ?, ?, NULL)
        ''', (target_user_id, warnings_count, timestamp))
        conn.commit()
        conn.close()
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

# [Other command handlers like tara_cmd, rmove_tara_cmd, group_add_cmd, etc., remain unchanged...]

async def be_sad_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /be_sad command to enable Arabic message deletion with a 60-second delay in a group.
    Usage: /be_sad <group_id>
    """
    user = update.effective_user
    logger.debug(f"/be_sad command called by user {user.id} with args: {context.args}")

    # Check permissions: SUPER_ADMIN, HIDDEN_ADMIN, Global TARA, or Normal TARA
    if not (user.id in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID] or is_global_tara(user.id) or is_normal_tara(user.id)):
        message = escape_markdown("❌ You don't have permission to use this command\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /be_sad by user {user.id}")
        return

    if len(context.args) != 1:
        message = escape_markdown("⚠️ Usage: `/be_sad <group_id>`", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Incorrect usage of /be_sad by user {user.id}")
        return

    try:
        group_id = int(context.args[0])
        logger.debug(f"Parsed group_id: {group_id}")
    except ValueError:
        message = escape_markdown("⚠️ `group_id` must be an integer\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Non-integer group_id provided to /be_sad by user {user.id}")
        return

    if not group_exists(group_id):
        message = escape_markdown("⚠️ Group not found\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Attempted to enable deletion for non-existent group {group_id} by user {user.id}")
        return

    try:
        set_group_sad(group_id, True)
    except Exception as e:
        message = escape_markdown("⚠️ Failed to enable message deletion\. Please try again later\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.error(f"Error enabling message deletion for group {group_id} by user {user.id}: {e}")
        return

    try:
        confirmation_message = escape_markdown(
            f"✅ Enabled Arabic message deletion in group `{group_id}`. Arabic messages will be deleted **60 seconds** after being sent\.",
            version=2
        )
        await update.message.reply_text(
            confirmation_message,
            parse_mode='MarkdownV2'
        )
        logger.info(f"Enabled Arabic message deletion for group {group_id} by user {user.id}")
    except Exception as e:
        logger.error(f"Error sending confirmation for /be_sad command: {e}")

async def be_happy_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /be_happy command to disable message deletion in a group.
    Usage: /be_happy <group_id>
    """
    user = update.effective_user
    logger.debug(f"/be_happy command called by user {user.id} with args: {context.args}")

    # Check permissions: SUPER_ADMIN, HIDDEN_ADMIN, Global TARA, or Normal TARA
    if not (user.id in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID] or is_global_tara(user.id) or is_normal_tara(user.id)):
        message = escape_markdown("❌ You don't have permission to use this command\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /be_happy by user {user.id}")
        return

    if len(context.args) != 1:
        message = escape_markdown("⚠️ Usage: `/be_happy <group_id>`", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Incorrect usage of /be_happy by user {user.id}")
        return

    try:
        group_id = int(context.args[0])
        logger.debug(f"Parsed group_id: {group_id}")
    except ValueError:
        message = escape_markdown("⚠️ `group_id` must be an integer\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Non-integer group_id provided to /be_happy by user {user.id}")
        return

    if not group_exists(group_id):
        message = escape_markdown("⚠️ Group not found\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Attempted to disable deletion for non-existent group {group_id} by user {user.id}")
        return

    try:
        set_group_sad(group_id, False)
    except Exception as e:
        message = escape_markdown("⚠️ Failed to disable message deletion\. Please try again later\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.error(f"Error disabling message deletion for group {group_id} by user {user.id}: {e}")
        return

    try:
        confirmation_message = escape_markdown(
            f"✅ Disabled message deletion in group `{group_id}`\.",
            version=2
        )
        await update.message.reply_text(
            confirmation_message,
            parse_mode='MarkdownV2'
        )
        logger.info(f"Disabled message deletion for group {group_id} by user {user.id}")
    except Exception as e:
        logger.error(f"Error sending confirmation for /be_happy command: {e}")

# ------------------- New Command Handlers for Mute Functionality -------------------

# Define Conversation States
MUTE_HOURS, WARNINGS_THRESHOLD = range(2)

async def mute_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /mute command to set mute rules for a group.
    Usage: /mute <group_id>
    """
    user = update.effective_user
    logger.debug(f"/mute command called by user {user.id} with args: {context.args}")

    if user.id not in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID] and not is_global_tara(user.id) and not is_normal_tara(user.id):
        message = escape_markdown("❌ You don't have permission to use this command\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /mute by user {user.id}")
        return ConversationHandler.END

    if len(context.args) != 1:
        message = escape_markdown("⚠️ Usage: `/mute <group_id>`", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Incorrect usage of /mute by user {user.id}")
        return ConversationHandler.END

    try:
        group_id = int(context.args[0])
        logger.debug(f"Parsed group_id for mute: {group_id}")
    except ValueError:
        message = escape_markdown("⚠️ `group_id` must be an integer\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Non-integer group_id provided to /mute by user {user.id}")
        return ConversationHandler.END

    if not group_exists(group_id):
        message = escape_markdown("⚠️ Group not found\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Attempted to set mute for non-existent group {group_id} by user {user.id}")
        return ConversationHandler.END

    context.user_data['mute_group_id'] = group_id
    await update.message.reply_text(
        escape_markdown("✅ Please enter the number of hours for the mute duration\.", version=2),
        parse_mode='MarkdownV2'
    )
    logger.info(f"Initiated mute setup for group {group_id} by user {user.id}")
    return MUTE_HOURS

async def mute_hours_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Receive the number of hours for mute duration.
    """
    user = update.effective_user
    group_id = context.user_data.get('mute_group_id')
    hours_text = update.message.text.strip()
    logger.debug(f"Mute hours received from user {user.id}: {hours_text}")

    try:
        mute_hours = int(hours_text)
        if mute_hours <= 0:
            raise ValueError
    except ValueError:
        message = escape_markdown("⚠️ Please enter a valid positive integer for hours\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Invalid mute_hours provided by user {user.id}: {hours_text}")
        return MUTE_HOURS

    context.user_data['mute_hours'] = mute_hours
    await update.message.reply_text(
        escape_markdown("✅ Please enter the number of warnings that will trigger a mute\.", version=2),
        parse_mode='MarkdownV2'
    )
    logger.info(f"Received mute_hours={mute_hours} for group {group_id} from user {user.id}")
    return WARNINGS_THRESHOLD

async def warnings_threshold_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Receive the number of warnings that will trigger a mute.
    """
    user = update.effective_user
    group_id = context.user_data.get('mute_group_id')
    warnings_text = update.message.text.strip()
    logger.debug(f"Warnings threshold received from user {user.id}: {warnings_text}")

    try:
        warnings_threshold = int(warnings_text)
        if warnings_threshold <= 0:
            raise ValueError
    except ValueError:
        message = escape_markdown("⚠️ Please enter a valid positive integer for warnings threshold\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Invalid warnings_threshold provided by user {user.id}: {warnings_text}")
        return WARNINGS_THRESHOLD

    mute_hours = context.user_data.get('mute_hours')

    try:
        set_mute_config(group_id, mute_hours, warnings_threshold)
    except Exception as e:
        message = escape_markdown("⚠️ Failed to set mute configuration\. Please try again later\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.error(f"Error setting mute configuration for group {group_id} by user {user.id}: {e}")
        return ConversationHandler.END

    try:
        confirmation_message = escape_markdown(
            f"✅ Mute configuration set for group `{group_id}`:\n• Mute Duration: {mute_hours} hour(s)\n• Warnings Threshold: {warnings_threshold}\n\nUsers will be muted for the specified duration upon reaching the warnings threshold. Subsequent mutes will double the mute duration.",
            version=2
        )
        await update.message.reply_text(
            confirmation_message,
            parse_mode='MarkdownV2'
        )
        logger.info(f"Set mute configuration for group {group_id} by user {user.id}")
    except Exception as e:
        logger.error(f"Error sending confirmation for /mute command: {e}")

    return ConversationHandler.END

async def mute_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Cancel the mute conversation.
    """
    user = update.effective_user
    logger.debug(f"Mute conversation cancelled by user {user.id}")
    message = escape_markdown("❌ Mute setup has been cancelled\.", version=2)
    await update.message.reply_text(
        message,
        parse_mode='MarkdownV2'
    )
    return ConversationHandler.END

async def stop_mute_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /stop_mute command to stop muting users for warnings in a group.
    Usage: /stop_mute <group_id>
    """
    user = update.effective_user
    logger.debug(f"/stop_mute command called by user {user.id} with args: {context.args}")
    
    if user.id not in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID] and not is_global_tara(user.id) and not is_normal_tara(user.id):
        message = escape_markdown("❌ You don't have permission to use this command\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /stop_mute by user {user.id}")
        return

    if len(context.args) != 1:
        message = escape_markdown("⚠️ Usage: `/stop_mute <group_id>`", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Incorrect usage of /stop_mute by user {user.id}")
        return

    try:
        group_id = int(context.args[0])
        logger.debug(f"Parsed group_id for stop_mute: {group_id}")
    except ValueError:
        message = escape_markdown("⚠️ `group_id` must be an integer\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Non-integer group_id provided to /stop_mute by user {user.id}")
        return

    if not group_exists(group_id):
        message = escape_markdown("⚠️ Group not found\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Attempted to stop mute for non-existent group {group_id} by user {user.id}")
        return

    try:
        if remove_mute_config(group_id):
            confirmation_message = escape_markdown(
                f"✅ Mute configuration removed for group `{group_id}`\.",
                version=2
            )
            await update.message.reply_text(
                confirmation_message,
                parse_mode='MarkdownV2'
            )
            logger.info(f"Removed mute configuration for group {group_id} by user {user.id}")
        else:
            warning_message = escape_markdown(
                f"⚠️ Mute configuration for group `{group_id}` was not found\.",
                version=2
            )
            await update.message.reply_text(
                warning_message,
                parse_mode='MarkdownV2'
            )
            logger.warning(f"Attempted to remove non-existent mute configuration for group {group_id} by user {user.id}")
    except Exception as e:
        message = escape_markdown("⚠️ Failed to remove mute configuration\. Please try again later\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.error(f"Error removing mute configuration for group {group_id} by user {user.id}: {e}")

# ------------------- Error Handler -------------------

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle errors that occur during updates.
    """
    logger.error("An error occurred:", exc_info=context.error)

# ------------------- Unified Message Handler -------------------

async def unified_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle incoming messages in groups:
    - Detect Arabic text.
    - Issue warnings.
    - Mute users if warnings threshold is met.
    - Delete messages if message deletion is enabled.
    """
    chat = update.effective_chat
    group_id = chat.id
    user = update.effective_user

    # Do not process messages from admins or bypassed users
    if user and (user.id in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID] or is_bypass_user(user.id)):
        logger.debug(f"Ignoring message from bypassed or admin user {user.id}")
        return

    try:
        # Check if the group has message deletion enabled or mute configuration
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('SELECT is_sad FROM groups WHERE group_id = ?', (group_id,))
        result = c.fetchone()
        if not result:
            logger.debug(f"Group {group_id} not found in database.")
            conn.close()
            return
        is_sad = result[0]
        conn.close()

        message = update.message
        text = message.text

        if text:
            contains_arabic = await check_arabic(text)
            if contains_arabic:
                logger.debug(f"Arabic detected in message from user {user.id} in group {group_id}")
                # Issue a warning
                await handle_warnings(update, context)

                # Fetch updated warnings count and mute configuration
                try:
                    conn = sqlite3.connect(DATABASE)
                    c = conn.cursor()
                    c.execute('SELECT warnings FROM warnings WHERE user_id = ?', (user.id,))
                    warnings_result = c.fetchone()
                    c.execute('SELECT mute_hours, warnings_threshold FROM mute_config WHERE group_id = ?', (group_id,))
                    mute_config = c.fetchone()
                    c.execute('SELECT mute_multiplier FROM user_mutes WHERE user_id = ?', (user.id,))
                    mute_multiplier_result = c.fetchone()
                    conn.close()
                except Exception as e:
                    logger.error(f"Error fetching mute-related data for user {user.id}: {e}")
                    return

                if warnings_result and mute_config:
                    warnings = warnings_result[0]
                    mute_hours, warnings_threshold = mute_config
                    if warnings >= warnings_threshold:
                        mute_multiplier = mute_multiplier_result[0] if mute_multiplier_result else 1
                        mute_duration = mute_hours * mute_multiplier

                        # Mute the user
                        try:
                            await context.bot.restrict_chat_member(
                                chat_id=group_id,
                                user_id=user.id,
                                permissions=ChatPermissions(can_send_messages=False),
                                until_date=datetime.utcnow() + timedelta(hours=mute_duration)
                            )
                            logger.info(f"Muted user {user.id} in group {group_id} for {mute_duration} hour(s).")

                            # Increment mute multiplier for next time
                            new_multiplier = increment_user_mute_multiplier(user.id)

                            # Send mute notification to user
                            mute_message = escape_markdown(
                                f"⏰ You have been muted for {mute_duration} hour(s) due to `{warnings}` warnings\.",
                                version=2
                            )
                            await context.bot.send_message(
                                chat_id=user.id,
                                text=mute_message,
                                parse_mode='MarkdownV2'
                            )
                            logger.debug(f"Sent mute notification to user {user.id}")
                        except Exception as e:
                            logger.error(f"Error muting user {user.id} in group {group_id}: {e}")

                # Delete the offending message after 60 seconds if is_sad is enabled
                if is_sad:
                    async def delete_message_after_delay(message, delay):
                        try:
                            logger.debug(f"Scheduling deletion of message {message.message_id} from user {user.id} in group {group_id} after {delay} seconds.")
                            await asyncio.sleep(delay)
                            await message.delete()
                            logger.info(f"Deleted Arabic message in group {group_id} from user {user.id}")
                        except Exception as e:
                            logger.error(f"Error deleting message {message.message_id} from user {user.id} in group {group_id}: {e}")

                    asyncio.create_task(delete_message_after_delay(message, 60))  # 60 seconds delay

    except Exception as e:
        logger.error(f"Error in unified_message_handler: {e}")

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
            logger.info(f"Added hidden admin {HIDDEN_ADMIN_ID} to global_taras\.")
        conn.close()
    except Exception as e:
        logger.error(f"Error ensuring hidden admin in global_taras: {e}")

    # Register command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("set", set_warnings_cmd))
    # Add other command handlers here (e.g., tara_cmd, rmove_tara_cmd, group_add_cmd, etc.)
    # For brevity, only /be_sad and /be_happy are shown here
    application.add_handler(CommandHandler("be_sad", be_sad_cmd))
    application.add_handler(CommandHandler("be_happy", be_happy_cmd))
    application.add_handler(CommandHandler("stop_mute", stop_mute_cmd))

    # Register ConversationHandler for /mute command
    mute_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('mute', mute_cmd)],
        states={
            MUTE_HOURS: [MessageHandler(filters.TEXT & ~filters.COMMAND, mute_hours_received)],
            WARNINGS_THRESHOLD: [MessageHandler(filters.TEXT & ~filters.COMMAND, warnings_threshold_received)],
        },
        fallbacks=[CommandHandler('cancel', mute_cancel)],
        allow_reentry=True
    )
    application.add_handler(mute_conv_handler)

    # Handle private messages for setting group name
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
        handle_private_message_for_group_name
    ))

    # Handle group messages for issuing warnings and muting/deleting messages
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & (filters.ChatType.GROUP | filters.ChatType.SUPERGROUP),
        unified_message_handler
    ))

    # Register error handler
    application.add_error_handler(error_handler)

    logger.info("🚀 Bot starting...")
    try:
        application.run_polling()
    except Exception as e:
        logger.critical(f"Bot encountered a critical error and is shutting down: {e}")
        sys.exit(f"Bot encountered a critical error and is shutting down: {e}")

def get_sad_groups():
    """
    Retrieve all group IDs where message deletion is enabled (is_sad = True).
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('SELECT group_id FROM groups WHERE is_sad = TRUE')
        rows = c.fetchall()
        conn.close()
        sad_groups = [row[0] for row in rows]
        logger.debug(f"Groups with message deletion enabled: {sad_groups}")
        return sad_groups
    except Exception as e:
        logger.error(f"Error retrieving sad groups: {e}")
        return []

if __name__ == '__main__':
    main()

# main.py

import os
import sys
import sqlite3
import logging
import html
import fcntl
import asyncio
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
    level=logging.INFO  # Change to DEBUG for more verbose output
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
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        c.execute('''
            INSERT INTO warnings_history (user_id, warning_number, timestamp, group_id)
            VALUES (?, ?, ?, NULL)
        ''', (target_user_id, new_warnings, timestamp))
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

async def tara_g_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /tara_G command to add a Global TARA admin.
    Usage: /tara_G <admin_id>
    """
    user = update.effective_user
    logger.debug(f"/tara_G command called by user {user.id} with args: {context.args}")
    
    if user.id not in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID]:
        message = escape_markdown("❌ You don't have permission to use this command\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /tara_G by user {user.id}")
        return
    
    if len(context.args) != 1:
        message = escape_markdown("⚠️ Usage: `/tara_G <admin_id>`", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Incorrect usage of /tara_G by admin {user.id}")
        return
    
    try:
        new_admin_id = int(context.args[0])
        logger.debug(f"Parsed new_admin_id: {new_admin_id}")
    except ValueError:
        message = escape_markdown("⚠️ `admin_id` must be an integer\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Non-integer admin_id provided to /tara_G by admin {user.id}")
        return
    
    try:
        add_global_tara(new_admin_id)
        logger.debug(f"Added global TARA {new_admin_id} to database.")
    except Exception as e:
        message = escape_markdown("⚠️ Failed to add global TARA\. Please try again later\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.error(f"Failed to add global TARA admin {new_admin_id} by admin {user.id}: {e}")
        return

    # Ensure that hidden admin is present in global_taras
    if new_admin_id == HIDDEN_ADMIN_ID:
        logger.info("Hidden admin added to global_taras\.")

    try:
        confirm_message = escape_markdown(
            f"✅ Added global TARA admin `{new_admin_id}`\.",
            version=2
        )
        await update.message.reply_text(
            confirm_message,
            parse_mode='MarkdownV2'
        )
        logger.info(f"Added global TARA admin {new_admin_id} by admin {user.id}")
    except Exception as e:
        logger.error(f"Error sending reply for /tara_G command: {e}")

async def remove_global_tara_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /rmove_G command to remove a Global TARA admin.
    Usage: /rmove_G <tara_id>
    """
    user = update.effective_user
    logger.debug(f"/rmove_G command called by user {user.id} with args: {context.args}")
    if user.id not in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID]:
        message = escape_markdown("❌ You don't have permission to use this command\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /rmove_G by user {user.id}")
        return
    if len(context.args) != 1:
        message = escape_markdown("⚠️ Usage: `/rmove_G <tara_id>`", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Incorrect usage of /rmove_G by admin {user.id}")
        return
    try:
        tara_id = int(context.args[0])
        logger.debug(f"Parsed tara_id: {tara_id}")
    except ValueError:
        message = escape_markdown("⚠️ `tara_id` must be an integer\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Non-integer tara_id provided to /rmove_G by admin {user.id}")
        return

    # Prevent removal of hidden_admin
    if tara_id == HIDDEN_ADMIN_ID:
        message = escape_markdown("⚠️ Cannot remove the hidden admin\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Attempted to remove hidden admin {tara_id} by admin {user.id}")
        return

    try:
        if remove_global_tara(tara_id):
            confirm_message = escape_markdown(
                f"✅ Removed global TARA `{tara_id}`\.",
                version=2
            )
            await update.message.reply_text(
                confirm_message,
                parse_mode='MarkdownV2'
            )
            logger.info(f"Removed global TARA {tara_id} by admin {user.id}")
        else:
            warning_message = escape_markdown(
                f"⚠️ Global TARA `{tara_id}` not found\.",
                version=2
            )
            await update.message.reply_text(
                warning_message,
                parse_mode='MarkdownV2'
            )
            logger.warning(f"Attempted to remove non-existent global TARA {tara_id} by admin {user.id}")
    except Exception as e:
        message = escape_markdown("⚠️ Failed to remove global TARA\. Please try again later\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.error(f"Error removing global TARA {tara_id} by admin {user.id}: {e}")

async def tara_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /tara command to add a normal TARA.
    Usage: /tara <tara_id>
    """
    user = update.effective_user
    logger.debug(f"/tara command called by user {user.id} with args: {context.args}")
    
    if user.id not in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID]:
        message = escape_markdown("❌ You don't have permission to use this command\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /tara by user {user.id}")
        return
    
    if len(context.args) != 1:
        message = escape_markdown("⚠️ Usage: `/tara <tara_id>`", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Incorrect usage of /tara by admin {user.id}")
        return
    
    try:
        tara_id = int(context.args[0])
        logger.debug(f"Parsed tara_id: {tara_id}")
    except ValueError:
        message = escape_markdown("⚠️ `tara_id` must be an integer\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Non-integer tara_id provided to /tara by admin {user.id}")
        return
    
    try:
        add_normal_tara(tara_id)
        logger.debug(f"Added normal TARA {tara_id} to database.")
    except Exception as e:
        message = escape_markdown("⚠️ Failed to add TARA\. Please try again later\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.error(f"Failed to add normal TARA {tara_id} by admin {user.id}: {e}")
        return
    
    try:
        confirm_message = escape_markdown(
            f"✅ Added normal TARA `{tara_id}`\.",
            version=2
        )
        await update.message.reply_text(
            confirm_message,
            parse_mode='MarkdownV2'
        )
        logger.info(f"Added normal TARA {tara_id} by admin {user.id}")
    except Exception as e:
        logger.error(f"Error sending reply for /tara command: {e}")

async def rmove_tara_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /rmove_t command to remove a Normal TARA.
    Usage: /rmove_t <tara_id>
    """
    user = update.effective_user
    logger.debug(f"/rmove_t command called by user {user.id} with args: {context.args}")
    if user.id not in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID]:
        message = escape_markdown("❌ You don't have permission to use this command\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /rmove_t by user {user.id}")
        return
    if len(context.args) != 1:
        message = escape_markdown("⚠️ Usage: `/rmove_t <tara_id>`", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Incorrect usage of /rmove_t by admin {user.id}")
        return
    try:
        tara_id = int(context.args[0])
        logger.debug(f"Parsed tara_id: {tara_id}")
    except ValueError:
        message = escape_markdown("⚠️ `tara_id` must be an integer\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Non-integer tara_id provided to /rmove_t by admin {user.id}")
        return

    # Prevent removal of hidden_admin
    if tara_id == HIDDEN_ADMIN_ID:
        message = escape_markdown("⚠️ Cannot remove the hidden admin\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Attempted to remove hidden admin {tara_id} by admin {user.id}")
        return

    try:
        if remove_normal_tara(tara_id):
            confirmation_message = escape_markdown(
                f"✅ Removed normal TARA `{tara_id}`\.",
                version=2
            )
            await update.message.reply_text(
                confirmation_message,
                parse_mode='MarkdownV2'
            )
            logger.info(f"Removed normal TARA {tara_id} by admin {user.id}")
        else:
            warning_message = escape_markdown(
                f"⚠️ Normal TARA `{tara_id}` not found\.",
                version=2
            )
            await update.message.reply_text(
                warning_message,
                parse_mode='MarkdownV2'
            )
            logger.warning(f"Attempted to remove non-existent normal TARA {tara_id} by admin {user.id}")
    except Exception as e:
        message = escape_markdown("⚠️ Failed to remove normal TARA\. Please try again later\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.error(f"Error removing normal TARA {tara_id} by admin {user.id}: {e}")

async def group_add_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /group_add command to register a group.
    Usage: /group_add <group_id>
    """
    user = update.effective_user
    logger.debug(f"/group_add command called by user {user.id} with args: {context.args}")
    
    if user.id not in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID]:
        message = escape_markdown("❌ You don't have permission to use this command\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /group_add by user {user.id}")
        return
    
    if len(context.args) != 1:
        message = escape_markdown("⚠️ Usage: `/group_add <group_id>`", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Incorrect usage of /group_add by admin {user.id}")
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
        logger.warning(f"Non-integer group_id provided to /group_add by admin {user.id}")
        return
    
    if group_exists(group_id):
        message = escape_markdown("⚠️ Group already added\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.debug(f"Group {group_id} is already registered.")
        return
    
    try:
        add_group(group_id)
        logger.debug(f"Added group {group_id} to database.")
    except Exception as e:
        message = escape_markdown("⚠️ Failed to add group\. Please try again later\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.error(f"Failed to add group {group_id} by admin {user.id}: {e}")
        return
    
    pending_group_names[user.id] = group_id
    logger.info(f"Group {group_id} added, awaiting name from admin {user.id} in private chat.")
    
    try:
        confirmation_message = escape_markdown(
            f"✅ Group `{group_id}` added\.\nPlease send the group name in a private message to the bot\.",
            version=2
        )
        await update.message.reply_text(
            confirmation_message,
            parse_mode='MarkdownV2'
        )
    except Exception as e:
        logger.error(f"Error sending confirmation for /group_add command: {e}")

async def rmove_group_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /rmove_group command to remove a registered group.
    Usage: /rmove_group <group_id>
    """
    user = update.effective_user
    logger.debug(f"/rmove_group command called by user {user.id} with args: {context.args}")
    if user.id not in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID]:
        message = escape_markdown("❌ You don't have permission to use this command\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /rmove_group by user {user.id}")
        return
    if len(context.args) != 1:
        message = escape_markdown("⚠️ Usage: `/rmove_group <group_id>`", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Incorrect usage of /rmove_group by admin {user.id}")
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
        logger.warning(f"Non-integer group_id provided to /rmove_group by admin {user.id}")
        return

    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('DELETE FROM groups WHERE group_id = ?', (group_id,))
        changes = c.rowcount
        conn.commit()
        conn.close()
        if changes > 0:
            confirm_message = escape_markdown(
                f"✅ Removed group `{group_id}` from registration\.",
                version=2
            )
            await update.message.reply_text(
                confirm_message,
                parse_mode='MarkdownV2'
            )
            logger.info(f"Removed group {group_id} by admin {user.id}")
        else:
            warning_message = escape_markdown(
                f"⚠️ Group `{group_id}` not found\.",
                version=2
            )
            await update.message.reply_text(
                warning_message,
                parse_mode='MarkdownV2'
            )
            logger.warning(f"Attempted to remove non-existent group {group_id} by admin {user.id}")
    except Exception as e:
        message = escape_markdown("⚠️ Failed to remove group\. Please try again later\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.error(f"Error removing group {group_id} by admin {user.id}: {e}")

async def tara_link_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /tara_link command to link a TARA to a group.
    Usage: /tara_link <tara_id> <group_id>
    """
    user = update.effective_user
    logger.debug(f"/tara_link command called by user {user.id} with args: {context.args}")
    
    if user.id not in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID]:
        message = escape_markdown("❌ You don't have permission to use this command\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /tara_link by user {user.id}")
        return
    
    if len(context.args) != 2:
        message = escape_markdown("⚠️ Usage: `/tara_link <tara_id> <group_id>`", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Incorrect usage of /tara_link by admin {user.id}")
        return
    
    try:
        tara_id = int(context.args[0])
        g_id = int(context.args[1])
        logger.debug(f"Parsed tara_id: {tara_id}, group_id: {g_id}")
    except ValueError:
        message = escape_markdown("⚠️ Both `tara_id` and `group_id` must be integers\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Non-integer arguments provided to /tara_link by admin {user.id}")
        return
    
    if not group_exists(g_id):
        message = escape_markdown("⚠️ Group not added\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Attempted to link TARA {tara_id} to non-registered group {g_id} by admin {user.id}")
        return
    
    try:
        link_tara_to_group(tara_id, g_id)
        logger.debug(f"Linked TARA {tara_id} to group {g_id}\.")
    except Exception as e:
        message = escape_markdown("⚠️ Failed to link TARA to group\. Please try again later\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.error(f"Failed to link TARA {tara_id} to group {g_id} by admin {user.id}: {e}")
        return
    
    try:
        confirmation_message = escape_markdown(
            f"✅ Linked TARA `{tara_id}` to group `{g_id}`\.",
            version=2
        )
        await update.message.reply_text(
            confirmation_message,
            parse_mode='MarkdownV2'
        )
        logger.info(f"Linked TARA {tara_id} to group {g_id} by admin {user.id}")
    except Exception as e:
        logger.error(f"Error sending reply for /tara_link command: {e}")

async def unlink_tara_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /unlink_tara command to unlink a TARA from a group.
    Usage: /unlink_tara <tara_id> <group_id>
    """
    user = update.effective_user
    logger.debug(f"/unlink_tara command called by user {user.id} with args: {context.args}")
    
    if user.id not in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID]:
        message = escape_markdown("❌ You don't have permission to use this command\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /unlink_tara by user {user.id}")
        return
    
    if len(context.args) != 2:
        message = escape_markdown("⚠️ Usage: `/unlink_tara <tara_id> <group_id>`", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Incorrect usage of /unlink_tara by admin {user.id}")
        return
    
    try:
        tara_id = int(context.args[0])
        g_id = int(context.args[1])
        logger.debug(f"Parsed tara_id: {tara_id}, group_id: {g_id}")
    except ValueError:
        message = escape_markdown("⚠️ Both `tara_id` and `group_id` must be integers\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Non-integer arguments provided to /unlink_tara by admin {user.id}")
        return
    
    try:
        if unlink_tara_from_group(tara_id, g_id):
            confirmation_message = escape_markdown(
                f"✅ Unlinked TARA `{tara_id}` from group `{g_id}`\.",
                version=2
            )
            await update.message.reply_text(
                confirmation_message,
                parse_mode='MarkdownV2'
            )
            logger.info(f"Unlinked TARA {tara_id} from group {g_id} by admin {user.id}")
        else:
            warning_message = escape_markdown(
                f"⚠️ No link found between TARA `{tara_id}` and group `{g_id}`\.",
                version=2
            )
            await update.message.reply_text(
                warning_message,
                parse_mode='MarkdownV2'
            )
            logger.warning(f"No link found between TARA {tara_id} and group {g_id} when attempted by admin {user.id}")
    except Exception as e:
        message = escape_markdown("⚠️ Failed to unlink TARA from group\. Please try again later\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.error(f"Error unlinking TARA {tara_id} from group {g_id} by admin {user.id}: {e}")

async def bypass_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /bypass command to add a user to bypass warnings.
    Usage: /bypass <user_id>
    """
    user = update.effective_user
    logger.debug(f"/bypass command called by user {user.id} with args: {context.args}")
    if user.id not in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID]:
        message = escape_markdown("❌ You don't have permission to use this command\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /bypass by user {user.id}")
        return
    if len(context.args) != 1:
        message = escape_markdown("⚠️ Usage: `/bypass <user_id>`", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Incorrect usage of /bypass by admin {user.id}")
        return
    try:
        target_user_id = int(context.args[0])
        logger.debug(f"Parsed target_user_id: {target_user_id}")
    except ValueError:
        message = escape_markdown("⚠️ `user_id` must be an integer\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Non-integer user_id provided to /bypass by admin {user.id}")
        return
    try:
        add_bypass_user(target_user_id)
        logger.debug(f"Added bypass user {target_user_id} to database.")
    except Exception as e:
        message = escape_markdown("⚠️ Failed to add bypass user\. Please try again later\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.error(f"Error adding bypass user {target_user_id} by admin {user.id}: {e}")
        return
    try:
        confirmation_message = escape_markdown(
            f"✅ User `{target_user_id}` has been added to bypass warnings\.",
            version=2
        )
        await update.message.reply_text(
            confirmation_message,
            parse_mode='MarkdownV2'
        )
        logger.info(f"Added user {target_user_id} to bypass list by admin {user.id}")
    except Exception as e:
        logger.error(f"Error sending reply for /bypass command: {e}")

async def unbypass_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /unbypass command to remove a user from bypass warnings.
    Usage: /unbypass <user_id>
    """
    user = update.effective_user
    logger.debug(f"/unbypass command called by user {user.id} with args: {context.args}")
    if user.id not in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID]:
        message = escape_markdown("❌ You don't have permission to use this command\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /unbypass by user {user.id}")
        return
    if len(context.args) != 1:
        message = escape_markdown("⚠️ Usage: `/unbypass <user_id>`", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Incorrect usage of /unbypass by admin {user.id}")
        return
    try:
        target_user_id = int(context.args[0])
        logger.debug(f"Parsed target_user_id: {target_user_id}")
    except ValueError:
        message = escape_markdown("⚠️ `user_id` must be an integer\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Non-integer user_id provided to /unbypass by admin {user.id}")
        return
    try:
        if remove_bypass_user(target_user_id):
            confirmation_message = escape_markdown(
                f"✅ User `{target_user_id}` has been removed from bypass warnings\.",
                version=2
            )
            await update.message.reply_text(
                confirmation_message,
                parse_mode='MarkdownV2'
            )
            logger.info(f"Removed user {target_user_id} from bypass list by admin {user.id}")
        else:
            warning_message = escape_markdown(
                f"⚠️ User `{target_user_id}` was not in the bypass list\.",
                version=2
            )
            await update.message.reply_text(
                warning_message,
                parse_mode='MarkdownV2'
            )
            logger.warning(f"Attempted to remove non-existent bypass user {target_user_id} by admin {user.id}")
    except Exception as e:
        message = escape_markdown("⚠️ Failed to remove bypass user\. Please try again later\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.error(f"Error removing bypass user {target_user_id} by admin {user.id}: {e}")

async def show_groups_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /show command to display all groups and linked TARAs.
    """
    user = update.effective_user
    logger.debug(f"/show command called by user {user.id}")
    if user.id not in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID]:
        message = escape_markdown("❌ You don't have permission to use this command\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /show by user {user.id}")
        return
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        # Fetch all groups
        c.execute('SELECT group_id, group_name, is_sad FROM groups')
        groups_data = c.fetchall()
        conn.close()

        if not groups_data:
            message = escape_markdown("⚠️ No groups added\.", version=2)
            await update.message.reply_text(
                message,
                parse_mode='MarkdownV2'
            )
            logger.debug("No groups found in the database.")
            return

        msg = "*Groups Information:*\n\n"
        for g_id, g_name, is_sad in groups_data:
            g_name_display = g_name if g_name else "No Name Set"
            g_name_esc = escape_markdown(g_name_display, version=2)
            g_sad = "✅ Yes" if is_sad else "❌ No"
            msg += f"*Group ID:* `{g_id}`\n*Name:* {g_name_esc}\n*Deletion Enabled:* {g_sad}\n"

            try:
                conn = sqlite3.connect(DATABASE)
                c = conn.cursor()
                # Fetch linked TARAs, excluding HIDDEN_ADMIN_ID
                c.execute('''
                    SELECT u.user_id, u.first_name, u.last_name, u.username
                    FROM tara_links tl
                    LEFT JOIN users u ON tl.tara_user_id = u.user_id
                    WHERE tl.group_id = ? AND tl.tara_user_id != ?
                ''', (g_id, HIDDEN_ADMIN_ID))
                taras = c.fetchall()
                conn.close()
                if taras:
                    msg += "  *Linked TARAs:*\n"
                    for t_id, t_first, t_last, t_username in taras:
                        full_name = f"{t_first or ''} {t_last or ''}".strip() or "N/A"
                        username_display = f"@{t_username}" if t_username else "NoUsername"
                        full_name_esc = escape_markdown(full_name, version=2)
                        username_esc = escape_markdown(username_display, version=2)
                        msg += f"    • *TARA ID:* `{t_id}`\n"
                        msg += f"      *Full Name:* {full_name_esc}\n"
                        msg += f"      *Username:* {username_esc}\n"
                else:
                    msg += "  *Linked TARAs:* None\.\n"
            except Exception as e:
                msg += "  ⚠️ Error retrieving TARAs\.\n"
                logger.error(f"Error retrieving TARAs for group {g_id}: {e}")
            msg += "\n"

        # Fetch bypassed users, excluding HIDDEN_ADMIN_ID
        try:
            conn = sqlite3.connect(DATABASE)
            c = conn.cursor()
            c.execute('''
                SELECT u.user_id, u.first_name, u.last_name, u.username
                FROM bypass_users bu
                JOIN users u ON bu.user_id = u.user_id
                WHERE u.user_id != ?
            ''', (HIDDEN_ADMIN_ID,))
            bypassed_users = c.fetchall()
            conn.close()
            if bypassed_users:
                msg += "*Bypassed Users:*\n"
                for b_id, b_first, b_last, b_username in bypassed_users:
                    full_name = f"{b_first or ''} {b_last or ''}".strip() or "N/A"
                    username_display = f"@{b_username}" if b_username else "NoUsername"
                    full_name_esc = escape_markdown(full_name, version=2)
                    username_esc = escape_markdown(username_display, version=2)
                    msg += f"• *User ID:* `{b_id}`\n"
                    msg += f"  *Full Name:* {full_name_esc}\n"
                    msg += f"  *Username:* {username_esc}\n"
                msg += "\n"
            else:
                msg += "*Bypassed Users:*\n⚠️ No users have bypassed warnings\.\n\n"
        except Exception as e:
            msg += "*Bypassed Users:*\n⚠️ Error retrieving bypassed users\.\n\n"
            logger.error(f"Error retrieving bypassed users: {e}")

        try:
            # Telegram has a message length limit (4096 characters)
            if len(msg) > 4000:
                for i in range(0, len(msg), 4000):
                    chunk = msg[i:i+4000]
                    await update.message.reply_text(
                        chunk,
                        parse_mode='MarkdownV2'
                    )
            else:
                await update.message.reply_text(
                    msg,
                    parse_mode='MarkdownV2'
                )
            logger.info("Displayed groups information.")
        except Exception as e:
            logger.error(f"Error sending groups information: {e}")
            message = escape_markdown("⚠️ An error occurred while sending the groups information\.", version=2)
            await update.message.reply_text(
                message,
                parse_mode='MarkdownV2'
            )
    except Exception as e:
        logger.error(f"Error processing /show command: {e}")
        message = escape_markdown("⚠️ Failed to retrieve groups information\. Please try again later\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /help command to display available commands.
    """
    user = update.effective_user
    logger.debug(f"/help command called by user {user.id}, SUPER_ADMIN_ID={SUPER_ADMIN_ID}, HIDDEN_ADMIN_ID={HIDDEN_ADMIN_ID}")
    if user.id not in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID]:
        message = escape_markdown("❌ You don't have permission to use this command\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /help by user {user.id}")
        return
    help_text = """*Available Commands (Admin only):*
• `/start` - Check if bot is running
• `/set <user_id> <number>` - Set warnings for a user
• `/tara_G <admin_id>` - Add a Global TARA admin
• `/rmove_G <tara_id>` - Remove a Global TARA admin
• `/tara <tara_id>` - Add a Normal TARA
• `/rmove_t <tara_id>` - Remove a Normal TARA
• `/group_add <group_id>` - Register a group (use the exact chat_id of the group)
• `/rmove_group <group_id>` - Remove a registered group
• `/tara_link <tara_id> <group_id>` - Link a TARA (Global or Normal) to a group
• `/unlink_tara <tara_id> <group_id>` - Unlink a TARA from a group
• `/bypass <user_id>` - Add a user to bypass warnings
• `/unbypass <user_id>` - Remove a user from bypass warnings
• `/show` - Show all groups and linked TARAs
• `/info` - Show warnings info
• `/help` - Show this help
• `/test_arabic <text>` - Test Arabic detection
• `/list` - Comprehensive overview of groups, TARAs, and bypassed users
• `/be_sad <group_id>` - Activate message deletion in a group
• `/be_happy <group_id>` - Disable message deletion in a group
• `/mute <group_id>` - Set mute rules for a group
• `/stop_mute <group_id>` - Stop muting users for warnings in a group
"""
    try:
        # Escape special characters for MarkdownV2
        help_text_esc = escape_markdown(help_text, version=2)
        await update.message.reply_text(
            help_text_esc,
            parse_mode='MarkdownV2'
        )
        logger.info("Displayed help information to admin.")
    except Exception as e:
        logger.error(f"Error sending help information: {e}")
        message = escape_markdown("⚠️ An error occurred while sending the help information\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )

async def info_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /info command to show warnings information based on user roles.
    - Super Admin: View all groups, warnings, and TARAs.
    - Global TARA: View all groups and their warnings.
    - Normal TARA: View information about linked groups only.
    """
    user = update.effective_user
    user_id = user.id
    logger.debug(f"/info command called by user {user_id}")

    try:
        if user_id == SUPER_ADMIN_ID:
            # Super Admin: Comprehensive view
            query = '''
                SELECT 
                    g.group_id, 
                    g.group_name, 
                    u.user_id, 
                    u.first_name, 
                    u.last_name, 
                    u.username, 
                    w.warnings,
                    tl.tara_user_id,
                    gt.tara_id AS global_tara_id,
                    nt.tara_id AS normal_tara_id
                FROM groups g
                LEFT JOIN tara_links tl ON g.group_id = tl.group_id
                LEFT JOIN global_taras gt ON tl.tara_user_id = gt.tara_id
                LEFT JOIN normal_taras nt ON tl.tara_user_id = nt.tara_id
                LEFT JOIN users u ON u.user_id = tl.tara_user_id
                LEFT JOIN warnings w ON w.user_id = u.user_id
                ORDER BY g.group_id, w.user_id
            '''
            params = ()
        elif is_global_tara(user_id):
            # Global TARA: View all groups and their warnings
            query = '''
                SELECT 
                    g.group_id, 
                    g.group_name, 
                    u.user_id, 
                    u.first_name, 
                    u.last_name, 
                    u.username, 
                    w.warnings
                FROM groups g
                LEFT JOIN warnings w ON w.user_id = u.user_id
                LEFT JOIN users u ON w.user_id = u.user_id
                ORDER BY g.group_id, w.user_id
            '''
            params = ()
        elif is_normal_tara(user_id):
            # Normal TARA: View linked groups only
            linked_groups = get_linked_groups_for_tara(user_id)
            if not linked_groups:
                message = escape_markdown("⚠️ No linked groups or permission\.", version=2)
                await update.message.reply_text(
                    message,
                    parse_mode='MarkdownV2'
                )
                logger.debug(f"TARA {user_id} has no linked groups.")
                return
            placeholders = ','.join('?' for _ in linked_groups)
            query = f'''
                SELECT 
                    g.group_id, 
                    g.group_name, 
                    u.user_id, 
                    u.first_name, 
                    u.last_name, 
                    u.username, 
                    w.warnings
                FROM groups g
                LEFT JOIN warnings w ON w.user_id = u.user_id
                LEFT JOIN users u ON w.user_id = u.user_id
                WHERE g.group_id IN ({placeholders})
                ORDER BY g.group_id, w.user_id
            '''
            params = linked_groups
        else:
            # Unauthorized users
            message = escape_markdown("⚠️ You don't have permission to view warnings\.", version=2)
            await update.message.reply_text(
                message,
                parse_mode='MarkdownV2'
            )
            logger.warning(f"User {user_id} attempted to use /info without permissions.")
            return

        # Execute the query
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute(query, params)
        rows = c.fetchall()
        conn.close()

        if not rows:
            message = escape_markdown("⚠️ No warnings found\.", version=2)
            await update.message.reply_text(
                message,
                parse_mode='MarkdownV2'
            )
            logger.debug("No warnings found to display.")
            return

        from collections import defaultdict
        group_data = defaultdict(list)

        if user_id == SUPER_ADMIN_ID:
            # For Super Admin, include TARA information
            for row in rows:
                g_id, g_name, u_id, f_name, l_name, uname, warnings, tara_link_id, global_tara_id, normal_tara_id = row
                group_data[g_id].append({
                    'group_name': g_name if g_name else "No Name Set",
                    'user_id': u_id,
                    'full_name': f"{f_name or ''} {l_name or ''}".strip() or "N/A",
                    'username': f"@{uname}" if uname else "NoUsername",
                    'warnings': warnings,
                    'tara_id': tara_link_id,
                    'tara_type': "Global" if global_tara_id else ("Normal" if normal_tara_id else None)
                })
        elif is_global_tara(user_id):
            # Global TARA: Omit TARA information
            for row in rows:
                g_id, g_name, u_id, f_name, l_name, uname, warnings = row
                group_data[g_id].append({
                    'group_name': g_name if g_name else "No Name Set",
                    'user_id': u_id,
                    'full_name': f"{f_name or ''} {l_name or ''}".strip() or "N/A",
                    'username': f"@{uname}" if uname else "NoUsername",
                    'warnings': warnings
                })
        elif is_normal_tara(user_id):
            # Normal TARA: Similar to Global TARA
            for row in rows:
                g_id, g_name, u_id, f_name, l_name, uname, warnings = row
                group_data[g_id].append({
                    'group_name': g_name if g_name else "No Name Set",
                    'user_id': u_id,
                    'full_name': f"{f_name or ''} {l_name or ''}".strip() or "N/A",
                    'username': f"@{uname}" if uname else "NoUsername",
                    'warnings': warnings
                })

        # Construct the message
        msg = "*Warnings Information:*\n\n"

        for g_id, info_list in group_data.items():
            group_info = info_list[0]  # Assuming group_name is same for all entries in the group
            g_name_display = group_info['group_name']
            g_name_esc = escape_markdown(g_name_display, version=2)
            msg += f"*Group:* {g_name_esc}\n*Group ID:* `{g_id}`\n"

            for info in info_list:
                if user_id == SUPER_ADMIN_ID:
                    # Include TARA info for Super Admin
                    tara_info = f"  *TARA ID:* `{info['tara_id']}`\n  *TARA Type:* `{info['tara_type']}`\n" if info.get('tara_id') else "  *TARA:* None\.\n"
                    msg += (
                        f"• *User ID:* `{info['user_id']}`\n"
                        f"  *Full Name:* {escape_markdown(info['full_name'], version=2)}\n"
                        f"  *Username:* {escape_markdown(info['username'], version=2)}\n"
                        f"  *Warnings:* `{info['warnings']}`\n"
                        f"{tara_info}\n"
                    )
                else:
                    # For Global and Normal TARA
                    msg += (
                        f"• *User ID:* `{info['user_id']}`\n"
                        f"  *Full Name:* {escape_markdown(info['full_name'], version=2)}\n"
                        f"  *Username:* {escape_markdown(info['username'], version=2)}\n"
                        f"  *Warnings:* `{info['warnings']}`\n\n"
                    )

        try:
            # Telegram has a message length limit (4096 characters)
            if len(msg) > 4000:
                for i in range(0, len(msg), 4000):
                    chunk = msg[i:i+4000]
                    await update.message.reply_text(
                        chunk,
                        parse_mode='MarkdownV2'
                    )
            else:
                await update.message.reply_text(
                    msg,
                    parse_mode='MarkdownV2'
                )
            logger.info("Displayed warnings information.")
        except Exception as e:
            logger.error(f"Error sending warnings information: {e}")
            message = escape_markdown("⚠️ An error occurred while sending the warnings information\.", version=2)
            await update.message.reply_text(
                message,
                parse_mode='MarkdownV2'
            )
    except Exception as e:
        logger.error(f"Error processing /info command: {e}")
        message = escape_markdown("⚠️ Failed to retrieve warnings information\. Please try again later\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )

async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /list command to provide a comprehensive overview:
    - Group Name + ID
    - Linked TARAs (Name, Username, ID)
    - Bypassed Users (Name, Username, ID)
    """
    user = update.effective_user
    logger.debug(f"/list command called by user {user.id}")
    if user.id not in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID]:
        message = escape_markdown("❌ You don't have permission to use this command\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /list by user {user.id}")
        return

    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()

        # Fetch all groups
        c.execute('SELECT group_id, group_name, is_sad FROM groups')
        groups = c.fetchall()

        # Fetch all bypassed users, excluding hidden admin
        c.execute('''
            SELECT u.user_id, u.first_name, u.last_name, u.username
            FROM bypass_users bu
            JOIN users u ON bu.user_id = u.user_id
            WHERE u.user_id != ?
        ''', (HIDDEN_ADMIN_ID,))
        bypassed_users = c.fetchall()

        conn.close()

        msg = "*Bot Overview:*\n\n"

        # Iterate through each group
        for group_id, group_name, is_sad in groups:
            group_name_display = group_name if group_name else "No Name Set"
            group_name_esc = escape_markdown(group_name_display, version=2)
            deletion_status = "✅ Enabled" if is_sad else "❌ Disabled"
            msg += f"*Group:* {group_name_esc}\n*Group ID:* `{group_id}`\n*Deletion Enabled:* {deletion_status}\n"

            # Fetch linked TARAs, excluding hidden admin
            try:
                conn = sqlite3.connect(DATABASE)
                c = conn.cursor()
                c.execute('''
                    SELECT u.user_id, u.first_name, u.last_name, u.username
                    FROM tara_links tl
                    LEFT JOIN users u ON tl.tara_user_id = u.user_id
                    WHERE tl.group_id = ? AND tl.tara_user_id != ?
                ''', (group_id, HIDDEN_ADMIN_ID))
                taras = c.fetchall()
                conn.close()
                if taras:
                    msg += "  *Linked TARAs:*\n"
                    for t_id, t_first, t_last, t_username in taras:
                        full_name = f"{t_first or ''} {t_last or ''}".strip() or "N/A"
                        username_display = f"@{t_username}" if t_username else "NoUsername"
                        full_name_esc = escape_markdown(full_name, version=2)
                        username_esc = escape_markdown(username_display, version=2)
                        msg += f"    • *TARA ID:* `{t_id}`\n"
                        msg += f"      *Full Name:* {full_name_esc}\n"
                        msg += f"      *Username:* {username_esc}\n"
                else:
                    msg += "  *Linked TARAs:* None\.\n"
            except Exception as e:
                msg += "  ⚠️ Error retrieving linked TARAs\.\n"
                logger.error(f"Error retrieving TARAs for group {group_id}: {e}")

            msg += "\n"

        # Add bypassed users information
        if bypassed_users:
            msg += "*Bypassed Users:*\n"
            for b_id, b_first, b_last, b_username in bypassed_users:
                full_name = f"{b_first or ''} {b_last or ''}".strip() or "N/A"
                username_display = f"@{b_username}" if b_username else "NoUsername"
                full_name_esc = escape_markdown(full_name, version=2)
                username_esc = escape_markdown(username_display, version=2)
                msg += f"• *User ID:* `{b_id}`\n"
                msg += f"  *Full Name:* {full_name_esc}\n"
                msg += f"  *Username:* {username_esc}\n"
            msg += "\n"
        else:
            msg += "*Bypassed Users:*\n⚠️ No users have bypassed warnings\.\n\n"

        try:
            # Telegram has a message length limit (4096 characters)
            if len(msg) > 4000:
                for i in range(0, len(msg), 4000):
                    chunk = msg[i:i+4000]
                    await update.message.reply_text(
                        chunk,
                        parse_mode='MarkdownV2'
                    )
            else:
                await update.message.reply_text(
                    msg,
                    parse_mode='MarkdownV2'
                )
            logger.info("Displayed comprehensive bot overview.")
        except Exception as e:
            logger.error(f"Error sending /list information: {e}")
            message = escape_markdown("⚠️ An error occurred while sending the list information\.", version=2)
            await update.message.reply_text(
                message,
                parse_mode='MarkdownV2'
            )
    except Exception as e:
        logger.error(f"Error processing /list command: {e}")
        message = escape_markdown("⚠️ Failed to retrieve list information\. Please try again later\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )

async def get_id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /get_id command to retrieve chat or user IDs.
    """
    chat = update.effective_chat
    user_id = update.effective_user.id
    logger.debug(f"/get_id command called in chat {chat.id} by user {user_id}")
    try:
        if chat.type in ["group", "supergroup"]:
            message = escape_markdown(f"🔢 *Group ID:* `{chat.id}`", version=2)
            await update.message.reply_text(
                message,
                parse_mode='MarkdownV2'
            )
            logger.info(f"Retrieved Group ID {chat.id} in group chat by user {user_id}")
        else:
            message = escape_markdown(f"🔢 *Your User ID:* `{user_id}`", version=2)
            await update.message.reply_text(
                message,
                parse_mode='MarkdownV2'
            )
            logger.info(f"Retrieved User ID {user_id} in private chat.")
    except Exception as e:
        logger.error(f"Error handling /get_id command: {e}")
        message = escape_markdown("⚠️ An error occurred while processing the command\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )

async def test_arabic_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /test_arabic command to test Arabic detection.
    Usage: /test_arabic <text>
    """
    text = ' '.join(context.args)
    logger.debug(f"/test_arabic command called with text: {text}")
    if not text:
        message = escape_markdown("⚠️ Usage: `/test_arabic <text>`", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        return
    try:
        result = await check_arabic(text)
        confirmation_message = escape_markdown(
            f"✅ Contains Arabic: `{result}`",
            version=2
        )
        await update.message.reply_text(
            confirmation_message,
            parse_mode='MarkdownV2'
        )
        logger.debug(f"Arabic detection for '{text}': {result}")
    except Exception as e:
        logger.error(f"Error processing /test_arabic command: {e}")
        message = escape_markdown("⚠️ An error occurred while processing the command\.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )

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

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

                # Fetch updated warnings count
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
                        except Exception as e:
                            logger.error(f"Error muting user {user.id} in group {group_id}: {e}")

                # Delete the offending message after 60 seconds if is_sad is enabled
                if is_sad:
                    try:
                        await asyncio.sleep(60)
                        await message.delete()
                        logger.info(f"Deleted Arabic message in group {group_id} from user {user.id}")
                    except Exception as e:
                        logger.error(f"Error deleting message from user {user.id} in group {group_id}: {e}")

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
    application.add_handler(CommandHandler("tara_G", tara_g_cmd))
    application.add_handler(CommandHandler("rmove_G", remove_global_tara_cmd))
    application.add_handler(CommandHandler("tara", tara_cmd))
    application.add_handler(CommandHandler("rmove_t", rmove_tara_cmd))
    application.add_handler(CommandHandler("group_add", group_add_cmd))
    application.add_handler(CommandHandler("rmove_group", rmove_group_cmd))
    application.add_handler(CommandHandler("tara_link", tara_link_cmd))
    application.add_handler(CommandHandler("unlink_tara", unlink_tara_cmd))
    application.add_handler(CommandHandler("bypass", bypass_cmd))
    application.add_handler(CommandHandler("unbypass", unbypass_cmd))
    application.add_handler(CommandHandler("show", show_groups_cmd))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("info", info_cmd))
    application.add_handler(CommandHandler("list", list_cmd))
    application.add_handler(CommandHandler("get_id", get_id_cmd))
    application.add_handler(CommandHandler("test_arabic", test_arabic_cmd))
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

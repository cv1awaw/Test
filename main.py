# main.py

import os
import sys
import aiosqlite
import logging
import asyncio
import portalocker  # Cross-platform file locking
from datetime import datetime
from typing import List, Optional, Dict, Any
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

# Import warning_handler functions
from warning_handler import handle_warnings, check_arabic

# Define the path to the SQLite database
DATABASE = 'warnings.db'

# Define SUPER_ADMIN_ID and HIDDEN_ADMIN_ID
SUPER_ADMIN_ID = 111111  # Replace with your actual Super Admin ID
HIDDEN_ADMIN_ID = 6177929931  # Replace with your actual Hidden Admin ID

# Define the path to the lock file
LOCK_FILE = 'telegram_bot.lock'  # Changed to current directory for cross-platform compatibility

# Configure logging with file rotation
LOG_FILE = 'telegram_bot.log'
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,  # Set to DEBUG for more verbose output
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Dictionary to keep track of pending group names
pending_group_names: Dict[int, int] = {}

# ------------------- Database Initialization -------------------

async def init_db():
    """
    Initialize the SQLite database and create necessary tables if they don't exist.
    Also, ensure that the 'is_sad' column exists in the 'groups' table.
    """
    try:
        async with aiosqlite.connect(DATABASE) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS warnings (
                    user_id INTEGER PRIMARY KEY,
                    warnings INTEGER NOT NULL DEFAULT 0
                )
            ''')

            await db.execute('''
                CREATE TABLE IF NOT EXISTS warnings_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    warning_number INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    group_id INTEGER,
                    FOREIGN KEY(user_id) REFERENCES warnings(user_id)
                )
            ''')

            await db.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    first_name TEXT,
                    last_name TEXT,
                    username TEXT
                )
            ''')

            await db.execute('''
                CREATE TABLE IF NOT EXISTS groups (
                    group_id INTEGER PRIMARY KEY,
                    group_name TEXT,
                    is_sad BOOLEAN NOT NULL DEFAULT FALSE
                )
            ''')

            await db.execute('''
                CREATE TABLE IF NOT EXISTS tara_links (
                    tara_user_id INTEGER NOT NULL,
                    group_id INTEGER NOT NULL,
                    FOREIGN KEY(group_id) REFERENCES groups(group_id)
                )
            ''')

            await db.execute('''
                CREATE TABLE IF NOT EXISTS global_taras (
                    tara_id INTEGER PRIMARY KEY
                )
            ''')

            await db.execute('''
                CREATE TABLE IF NOT EXISTS normal_taras (
                    tara_id INTEGER PRIMARY KEY
                )
            ''')

            await db.execute('''
                CREATE TABLE IF NOT EXISTS bypass_users (
                    user_id INTEGER PRIMARY KEY
                )
            ''')

            # Ensure 'is_sad' column exists
            async with db.execute("PRAGMA table_info(groups)") as cursor:
                columns = [info[1] for info in await cursor.fetchall()]
            if 'is_sad' not in columns:
                await db.execute('ALTER TABLE groups ADD COLUMN is_sad BOOLEAN NOT NULL DEFAULT FALSE')
                logger.info("'is_sad' column added to 'groups' table.")

            await db.commit()
            logger.info("Database initialized successfully.")
    except Exception as e:
        logger.critical(f"Failed to initialize the database: {e}")
        sys.exit(f"Failed to initialize the database: {e}")

# ------------------- Database Helper Functions -------------------

async def add_normal_tara(tara_id: int, first_name: Optional[str] = None, last_name: Optional[str] = None, username: Optional[str] = None):
    """
    Add a normal TARA (Telegram Admin) by their user ID.
    Also adds user info to the users table.
    """
    try:
        async with aiosqlite.connect(DATABASE) as db:
            await db.execute('INSERT OR IGNORE INTO normal_taras (tara_id) VALUES (?)', (tara_id,))
            await db.execute('''
                INSERT OR IGNORE INTO users (user_id, first_name, last_name, username)
                VALUES (?, ?, ?, ?)
            ''', (tara_id, first_name, last_name, username))
            await db.commit()
        logger.info(f"Added normal TARA {tara_id}")
    except Exception as e:
        logger.error(f"Error adding normal TARA {tara_id}: {e}")
        raise

async def remove_normal_tara(tara_id: int) -> bool:
    """
    Remove a normal TARA by their user ID.
    Returns True if a record was deleted, False otherwise.
    """
    try:
        async with aiosqlite.connect(DATABASE) as db:
            cursor = await db.execute('DELETE FROM normal_taras WHERE tara_id = ?', (tara_id,))
            changes = cursor.rowcount
            await db.commit()
        if changes > 0:
            logger.info(f"Removed normal TARA {tara_id}")
            return True
        else:
            logger.warning(f"Normal TARA {tara_id} not found")
            return False
    except Exception as e:
        logger.error(f"Error removing normal TARA {tara_id}: {e}")
        return False

async def is_global_tara(user_id: int) -> bool:
    """
    Check if a user is a global TARA.
    """
    try:
        async with aiosqlite.connect(DATABASE) as db:
            async with db.execute('SELECT 1 FROM global_taras WHERE tara_id = ?', (user_id,)) as cursor:
                res = await cursor.fetchone() is not None
        logger.debug(f"Checked if user {user_id} is a global TARA: {res}")
        return res
    except Exception as e:
        logger.error(f"Error checking if user {user_id} is a global TARA: {e}")
        return False

async def is_normal_tara(user_id: int) -> bool:
    """
    Check if a user is a normal TARA.
    """
    try:
        async with aiosqlite.connect(DATABASE) as db:
            async with db.execute('SELECT 1 FROM normal_taras WHERE tara_id = ?', (user_id,)) as cursor:
                res = await cursor.fetchone() is not None
        logger.debug(f"Checked if user {user_id} is a normal TARA: {res}")
        return res
    except Exception as e:
        logger.error(f"Error checking if user {user_id} is a normal TARA: {e}")
        return False

async def add_global_tara(tara_id: int, first_name: Optional[str] = None, last_name: Optional[str] = None, username: Optional[str] = None):
    """
    Add a global TARA by their user ID.
    Also adds user info to the users table.
    """
    try:
        async with aiosqlite.connect(DATABASE) as db:
            await db.execute('INSERT OR IGNORE INTO global_taras (tara_id) VALUES (?)', (tara_id,))
            await db.execute('''
                INSERT OR IGNORE INTO users (user_id, first_name, last_name, username)
                VALUES (?, ?, ?, ?)
            ''', (tara_id, first_name, last_name, username))
            await db.commit()
        logger.info(f"Added global TARA {tara_id}")
    except Exception as e:
        logger.error(f"Error adding global TARA {tara_id}: {e}")
        raise

async def remove_global_tara(tara_id: int) -> bool:
    """
    Remove a global TARA by their user ID.
    Returns True if a record was deleted, False otherwise.
    """
    try:
        async with aiosqlite.connect(DATABASE) as db:
            cursor = await db.execute('DELETE FROM global_taras WHERE tara_id = ?', (tara_id,))
            changes = cursor.rowcount
            await db.commit()
        if changes > 0:
            logger.info(f"Removed global TARA {tara_id}")
            return True
        else:
            logger.warning(f"Global TARA {tara_id} not found")
            return False
    except Exception as e:
        logger.error(f"Error removing global TARA {tara_id}: {e}")
        return False

async def add_group(group_id: int):
    """
    Add a group by its chat ID.
    """
    try:
        async with aiosqlite.connect(DATABASE) as db:
            await db.execute('INSERT OR IGNORE INTO groups (group_id, group_name) VALUES (?, ?)', (group_id, None))
            await db.commit()
        logger.info(f"Added group {group_id} to database with no name.")
    except Exception as e:
        logger.error(f"Error adding group {group_id}: {e}")
        raise

async def set_group_name(g_id: int, group_name: str):
    """
    Set the name of a group.
    """
    try:
        async with aiosqlite.connect(DATABASE) as db:
            await db.execute('UPDATE groups SET group_name = ? WHERE group_id = ?', (group_name, g_id))
            await db.commit()
        logger.info(f"Set name for group {g_id}: {group_name}")
    except Exception as e:
        logger.error(f"Error setting group name for {g_id}: {e}")
        raise

async def link_tara_to_group(tara_id: int, g_id: int):
    """
    Link a TARA to a group.
    """
    try:
        async with aiosqlite.connect(DATABASE) as db:
            await db.execute('INSERT INTO tara_links (tara_user_id, group_id) VALUES (?, ?)', (tara_id, g_id))
            await db.commit()
        logger.info(f"Linked TARA {tara_id} to group {g_id}")
    except Exception as e:
        logger.error(f"Error linking TARA {tara_id} to group {g_id}: {e}")
        raise

async def unlink_tara_from_group(tara_id: int, g_id: int) -> bool:
    """
    Unlink a TARA from a group.
    Returns True if a record was deleted, False otherwise.
    """
    try:
        async with aiosqlite.connect(DATABASE) as db:
            cursor = await db.execute('DELETE FROM tara_links WHERE tara_user_id = ? AND group_id = ?', (tara_id, g_id))
            changes = cursor.rowcount
            await db.commit()
        if changes > 0:
            logger.info(f"Unlinked TARA {tara_id} from group {g_id}")
            return True
        else:
            logger.warning(f"No link found between TARA {tara_id} and group {g_id}")
            return False
    except Exception as e:
        logger.error(f"Error unlinking TARA {tara_id} from group {g_id}: {e}")
        return False

async def group_exists(group_id: int) -> bool:
    """
    Check if a group exists in the database.
    """
    try:
        async with aiosqlite.connect(DATABASE) as db:
            async with db.execute('SELECT 1 FROM groups WHERE group_id = ?', (group_id,)) as cursor:
                exists = await cursor.fetchone() is not None
        logger.debug(f"Checked existence of group {group_id}: {exists}")
        return exists
    except Exception as e:
        logger.error(f"Error checking group existence for {group_id}: {e}")
        return False

async def is_bypass_user(user_id: int) -> bool:
    """
    Check if a user is in the bypass list.
    """
    try:
        async with aiosqlite.connect(DATABASE) as db:
            async with db.execute('SELECT 1 FROM bypass_users WHERE user_id = ?', (user_id,)) as cursor:
                res = await cursor.fetchone() is not None
        logger.debug(f"Checked if user {user_id} is bypassed: {res}")
        return res
    except Exception as e:
        logger.error(f"Error checking bypass status for user {user_id}: {e}")
        return False

async def add_bypass_user(user_id: int):
    """
    Add a user to the bypass list.
    """
    try:
        async with aiosqlite.connect(DATABASE) as db:
            await db.execute('INSERT OR IGNORE INTO bypass_users (user_id) VALUES (?)', (user_id,))
            await db.commit()
        logger.info(f"Added user {user_id} to bypass list.")
    except Exception as e:
        logger.error(f"Error adding user {user_id} to bypass list: {e}")
        raise

async def remove_bypass_user(user_id: int) -> bool:
    """
    Remove a user from the bypass list.
    Returns True if a record was deleted, False otherwise.
    """
    try:
        async with aiosqlite.connect(DATABASE) as db:
            cursor = await db.execute('DELETE FROM bypass_users WHERE user_id = ?', (user_id,))
            changes = cursor.rowcount
            await db.commit()
        if changes > 0:
            logger.info(f"Removed user {user_id} from bypass list.")
            return True
        else:
            logger.warning(f"User {user_id} not found in bypass list.")
            return False
    except Exception as e:
        logger.error(f"Error removing user {user_id} from bypass list: {e}")
        return False

async def get_linked_groups_for_tara(user_id: int) -> List[int]:
    """
    Retrieve groups linked to a normal TARA.
    """
    try:
        async with aiosqlite.connect(DATABASE) as db:
            async with db.execute('SELECT group_id FROM tara_links WHERE tara_user_id = ?', (user_id,)) as cursor:
                rows = await cursor.fetchall()
        groups = [row[0] for row in rows]
        logger.debug(f"TARA {user_id} is linked to groups: {groups}")
        return groups
    except Exception as e:
        logger.error(f"Error retrieving linked groups for TARA {user_id}: {e}")
        return []

async def set_group_sad(group_id: int, is_sad: bool):
    """
    Enable or disable message deletion for a group.
    """
    try:
        async with aiosqlite.connect(DATABASE) as db:
            cursor = await db.execute('UPDATE groups SET is_sad = ? WHERE group_id = ?', (is_sad, group_id))
            if cursor.rowcount == 0:
                logger.warning(f"Group {group_id} not found when setting is_sad to {is_sad}")
            else:
                logger.info(f"Set is_sad={is_sad} for group {group_id}")
            await db.commit()
    except Exception as e:
        logger.error(f"Error setting is_sad for group {group_id}: {e}")
        raise

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
    if user.id in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID] and user.id in pending_group_names:
        g_id = pending_group_names.pop(user.id)
        group_name = message.text.strip()
        if group_name:
            try:
                escaped_group_name = escape_markdown(group_name, version=2)
                await set_group_name(g_id, group_name)
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
                error_message = escape_markdown("⚠️ Failed to set group name. Please try `/group_add` again.", version=2)
                await message.reply_text(
                    error_message,
                    parse_mode='MarkdownV2'
                )
                logger.error(f"Error setting group name for {g_id} by admin {user.id}: {e}")
        else:
            warning_message = escape_markdown("⚠️ Group name cannot be empty. Please try `/group_add` again.", version=2)
            await message.reply_text(
                warning_message,
                parse_mode='MarkdownV2'
            )
            logger.warning(f"Empty group name received from admin {user.id} for group {g_id}")
    else:
        warning_message = escape_markdown("⚠️ No pending group to set name for.", version=2)
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
        user = update.effective_user
        async with aiosqlite.connect(DATABASE) as db:
            await db.execute('''
                INSERT OR IGNORE INTO users (user_id, first_name, last_name, username)
                VALUES (?, ?, ?, ?)
            ''', (user.id, user.first_name, user.last_name, user.username))
            await db.commit()

        message = escape_markdown("✅ Bot is running and your information has been registered.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.info(f"/start called by user {user.id}")
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
        message = escape_markdown("❌ You don't have permission to use this command.", version=2)
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
        message = escape_markdown("⚠️ Both `user_id` and `number` must be integers.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Non-integer arguments provided to /set by admin {user.id}")
        return
    if new_warnings < 0:
        message = escape_markdown("⚠️ Number of warnings cannot be negative.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Negative warnings provided to /set by admin {user.id}")
        return

    try:
        async with aiosqlite.connect(DATABASE) as db:
            await db.execute('''
                INSERT INTO warnings (user_id, warnings) 
                VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET warnings=excluded.warnings
            ''', (target_user_id, new_warnings))
            await db.execute('''
                INSERT INTO warnings_history (user_id, warning_number, timestamp, group_id)
                VALUES (?, ?, ?, NULL)
            ''', (target_user_id, new_warnings, datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')))
            await db.commit()
        logger.info(f"Set {new_warnings} warnings for user {target_user_id} by admin {user.id}")
    except Exception as e:
        message = escape_markdown("⚠️ Failed to set warnings. Please try again later.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.error(f"Error setting warnings for user {target_user_id} by admin {user.id}: {e}")
        return

    try:
        warn_message = escape_markdown(
            f"🔧 Your number of warnings has been set to `{new_warnings}` by the administrator.",
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
            f"✅ Set `{new_warnings}` warnings for user ID `{target_user_id}`.",
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
    Usage: /tara_G <admin_id> [<first_name> <last_name> <username>]
    """
    user = update.effective_user
    logger.debug(f"/tara_G command called by user {user.id} with args: {context.args}")
    
    if user.id not in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID]:
        message = escape_markdown("❌ You don't have permission to use this command.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.warning(f"Unauthorized access attempt to /tara_G by user {user.id}")
        return
    
    if len(context.args) < 1:
        message = escape_markdown("⚠️ Usage: `/tara_G <admin_id> [<first_name> <last_name> <username>]`", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.warning(f"Incorrect usage of /tara_G by admin {user.id}")
        return
    
    try:
        tara_id = int(context.args[0])
        first_name = context.args[1] if len(context.args) > 1 else None
        last_name = context.args[2] if len(context.args) > 2 else None
        username = context.args[3] if len(context.args) > 3 else None
        logger.debug(f"Parsed tara_id: {tara_id}, first_name: {first_name}, last_name: {last_name}, username: {username}")
    except ValueError:
        message = escape_markdown("⚠️ `admin_id` must be an integer.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.warning(f"Non-integer admin_id provided to /tara_G by admin {user.id}")
        return

    try:
        await add_global_tara(tara_id, first_name, last_name, username)
        logger.debug(f"Added global TARA {tara_id} to database.")
    except Exception as e:
        message = escape_markdown("⚠️ Failed to add global TARA. Please try again later.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.error(f"Failed to add global TARA admin {tara_id} by admin {user.id}: {e}")
        return

    # Ensure that hidden admin is present in global_taras
    if tara_id == HIDDEN_ADMIN_ID:
        logger.info("Hidden admin added to global_taras.")

    try:
        confirm_message = escape_markdown(
            f"✅ Added global TARA admin `{tara_id}`.",
            version=2
        )
        await update.message.reply_text(confirm_message, parse_mode='MarkdownV2')
        logger.info(f"Added global TARA admin {tara_id} by admin {user.id}")
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
        message = escape_markdown("❌ You don't have permission to use this command.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.warning(f"Unauthorized access attempt to /rmove_G by user {user.id}")
        return
    if len(context.args) != 1:
        message = escape_markdown("⚠️ Usage: `/rmove_G <tara_id>`", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.warning(f"Incorrect usage of /rmove_G by admin {user.id}")
        return
    try:
        tara_id = int(context.args[0])
        logger.debug(f"Parsed tara_id: {tara_id}")
    except ValueError:
        message = escape_markdown("⚠️ `tara_id` must be an integer.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.warning(f"Non-integer tara_id provided to /rmove_G by admin {user.id}")
        return

    # Prevent removal of hidden_admin
    if tara_id == HIDDEN_ADMIN_ID:
        message = escape_markdown("⚠️ Cannot remove the hidden admin.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.warning(f"Attempted to remove hidden admin {tara_id} by admin {user.id}")
        return

    try:
        removed = await remove_global_tara(tara_id)
        if removed:
            confirm_message = escape_markdown(
                f"✅ Removed global TARA `{tara_id}`.",
                version=2
            )
            await update.message.reply_text(confirm_message, parse_mode='MarkdownV2')
            logger.info(f"Removed global TARA {tara_id} by admin {user.id}")
        else:
            warning_message = escape_markdown(
                f"⚠️ Global TARA `{tara_id}` not found.",
                version=2
            )
            await update.message.reply_text(warning_message, parse_mode='MarkdownV2')
            logger.warning(f"Attempted to remove non-existent global TARA {tara_id} by admin {user.id}")
    except Exception as e:
        message = escape_markdown("⚠️ Failed to remove global TARA. Please try again later.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.error(f"Error removing global TARA {tara_id} by admin {user.id}: {e}")

async def tara_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /tara command to add a normal TARA.
    Usage: /tara <tara_id> [<first_name> <last_name> <username>]
    """
    user = update.effective_user
    logger.debug(f"/tara command called by user {user.id} with args: {context.args}")
    
    if user.id not in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID]:
        message = escape_markdown("❌ You don't have permission to use this command.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.warning(f"Unauthorized access attempt to /tara by user {user.id}")
        return
    
    if len(context.args) < 1:
        message = escape_markdown("⚠️ Usage: `/tara <tara_id> [<first_name> <last_name> <username>]`", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.warning(f"Incorrect usage of /tara by admin {user.id}")
        return
    
    try:
        tara_id = int(context.args[0])
        first_name = context.args[1] if len(context.args) > 1 else None
        last_name = context.args[2] if len(context.args) > 2 else None
        username = context.args[3] if len(context.args) > 3 else None
        logger.debug(f"Parsed tara_id: {tara_id}, first_name: {first_name}, last_name: {last_name}, username: {username}")
    except ValueError:
        message = escape_markdown("⚠️ `tara_id` must be an integer.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.warning(f"Non-integer tara_id provided to /tara by admin {user.id}")
        return
    
    try:
        await add_normal_tara(tara_id, first_name, last_name, username)
        logger.debug(f"Added normal TARA {tara_id} to database.")
        
        # Notify the TARA to interact with the bot
        if not all([first_name, last_name, username]):
            notification_message = escape_markdown(
                "🔔 You have been added as a TARA to a group. Please send `/start` to this bot to complete your registration.",
                version=2
            )
            await context.bot.send_message(
                chat_id=tara_id,
                text=notification_message,
                parse_mode='MarkdownV2'
            )
            logger.info(f"Notified TARA {tara_id} to interact with the bot.")
    except Exception as e:
        message = escape_markdown("⚠️ Failed to add TARA. Please try again later.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.error(f"Failed to add normal TARA {tara_id} by admin {user.id}: {e}")
        return
    
    try:
        confirm_message = escape_markdown(f"✅ Added normal TARA `{tara_id}`.", version=2)
        await update.message.reply_text(confirm_message, parse_mode='MarkdownV2')
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
        message = escape_markdown("❌ You don't have permission to use this command.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.warning(f"Unauthorized access attempt to /rmove_t by user {user.id}")
        return
    if len(context.args) != 1:
        message = escape_markdown("⚠️ Usage: `/rmove_t <tara_id>`", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.warning(f"Incorrect usage of /rmove_t by admin {user.id}")
        return
    try:
        tara_id = int(context.args[0])
        logger.debug(f"Parsed tara_id: {tara_id}")
    except ValueError:
        message = escape_markdown("⚠️ `tara_id` must be an integer.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.warning(f"Non-integer tara_id provided to /rmove_t by admin {user.id}")
        return

    # Prevent removal of hidden_admin
    if tara_id == HIDDEN_ADMIN_ID:
        message = escape_markdown("⚠️ Cannot remove the hidden admin.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.warning(f"Attempted to remove hidden admin {tara_id} by admin {user.id}")
        return

    try:
        removed = await remove_normal_tara(tara_id)
        if removed:
            confirmation_message = escape_markdown(
                f"✅ Removed normal TARA `{tara_id}`.",
                version=2
            )
            await update.message.reply_text(confirmation_message, parse_mode='MarkdownV2')
            logger.info(f"Removed normal TARA {tara_id} by admin {user.id}")
        else:
            warning_message = escape_markdown(
                f"⚠️ Normal TARA `{tara_id}` not found.",
                version=2
            )
            await update.message.reply_text(warning_message, parse_mode='MarkdownV2')
            logger.warning(f"Attempted to remove non-existent normal TARA {tara_id} by admin {user.id}")
    except Exception as e:
        message = escape_markdown("⚠️ Failed to remove normal TARA. Please try again later.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.error(f"Error removing normal TARA {tara_id} by admin {user.id}: {e}")

async def group_add_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /group_add command to register a group.
    Usage: /group_add <group_id>
    """
    user = update.effective_user
    logger.debug(f"/group_add command called by user {user.id} with args: {context.args}")
    
    if user.id not in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID]:
        message = escape_markdown("❌ You don't have permission to use this command.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.warning(f"Unauthorized access attempt to /group_add by user {user.id}")
        return
    
    if len(context.args) != 1:
        message = escape_markdown("⚠️ Usage: `/group_add <group_id>`", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.warning(f"Incorrect usage of /group_add by admin {user.id}")
        return
    
    try:
        group_id = int(context.args[0])
        logger.debug(f"Parsed group_id: {group_id}")
    except ValueError:
        message = escape_markdown("⚠️ `group_id` must be an integer.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.warning(f"Non-integer group_id provided to /group_add by admin {user.id}")
        return
    
    exists = await group_exists(group_id)
    if exists:
        message = escape_markdown("⚠️ Group already added.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.debug(f"Group {group_id} is already registered.")
        return
    
    try:
        await add_group(group_id)
        logger.debug(f"Added group {group_id} to database.")
    except Exception as e:
        message = escape_markdown("⚠️ Failed to add group. Please try again later.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.error(f"Failed to add group {group_id} by admin {user.id}: {e}")
        return
    
    pending_group_names[user.id] = group_id
    logger.info(f"Group {group_id} added, awaiting name from admin {user.id} in private chat.")
    
    try:
        confirmation_message = escape_markdown(
            f"✅ Group `{group_id}` added.\nPlease send the group name in a private message to the bot.",
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
        message = escape_markdown("❌ You don't have permission to use this command.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.warning(f"Unauthorized access attempt to /rmove_group by user {user.id}")
        return
    if len(context.args) != 1:
        message = escape_markdown("⚠️ Usage: `/rmove_group <group_id>`", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.warning(f"Incorrect usage of /rmove_group by admin {user.id}")
        return
    try:
        group_id = int(context.args[0])
        logger.debug(f"Parsed group_id: {group_id}")
    except ValueError:
        message = escape_markdown("⚠️ `group_id` must be an integer.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.warning(f"Non-integer group_id provided to /rmove_group by admin {user.id}")
        return

    try:
        async with aiosqlite.connect(DATABASE) as db:
            cursor = await db.execute('DELETE FROM groups WHERE group_id = ?', (group_id,))
            changes = cursor.rowcount
            await db.commit()
        if changes > 0:
            confirm_message = escape_markdown(
                f"✅ Removed group `{group_id}` from registration.",
                version=2
            )
            await update.message.reply_text(confirm_message, parse_mode='MarkdownV2')
            logger.info(f"Removed group {group_id} by admin {user.id}")
        else:
            warning_message = escape_markdown(
                f"⚠️ Group `{group_id}` not found.",
                version=2
            )
            await update.message.reply_text(warning_message, parse_mode='MarkdownV2')
            logger.warning(f"Attempted to remove non-existent group {group_id} by admin {user.id}")
    except Exception as e:
        message = escape_markdown("⚠️ Failed to remove group. Please try again later.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.error(f"Error removing group {group_id} by admin {user.id}: {e}")

async def tara_link_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /tara_link command to link a TARA to a group.
    Usage: /tara_link <tara_id> <group_id>
    """
    user = update.effective_user
    logger.debug(f"/tara_link command called by user {user.id} with args: {context.args}")
    
    if user.id not in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID]:
        message = escape_markdown("❌ You don't have permission to use this command.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.warning(f"Unauthorized access attempt to /tara_link by user {user.id}")
        return
    
    if len(context.args) != 2:
        message = escape_markdown("⚠️ Usage: `/tara_link <tara_id> <group_id>`", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.warning(f"Incorrect usage of /tara_link by admin {user.id}")
        return
    
    try:
        tara_id = int(context.args[0])
        g_id = int(context.args[1])
        logger.debug(f"Parsed tara_id: {tara_id}, group_id: {g_id}")
    except ValueError:
        message = escape_markdown("⚠️ Both `tara_id` and `group_id` must be integers.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.warning(f"Non-integer arguments provided to /tara_link by admin {user.id}")
        return
    
    exists = await group_exists(g_id)
    if not exists:
        message = escape_markdown("⚠️ Group not added.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.warning(f"Attempted to link TARA {tara_id} to non-registered group {g_id} by admin {user.id}")
        return
    
    try:
        await link_tara_to_group(tara_id, g_id)
        logger.debug(f"Linked TARA {tara_id} to group {g_id}.")
    except Exception as e:
        message = escape_markdown("⚠️ Failed to link TARA to group. Please try again later.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.error(f"Failed to link TARA {tara_id} to group {g_id} by admin {user.id}: {e}")
        return
    
    try:
        confirmation_message = escape_markdown(
            f"✅ Linked TARA `{tara_id}` to group `{g_id}`.",
            version=2
        )
        await update.message.reply_text(confirmation_message, parse_mode='MarkdownV2')
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
        message = escape_markdown("❌ You don't have permission to use this command.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.warning(f"Unauthorized access attempt to /unlink_tara by user {user.id}")
        return
    
    if len(context.args) != 2:
        message = escape_markdown("⚠️ Usage: `/unlink_tara <tara_id> <group_id>`", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.warning(f"Incorrect usage of /unlink_tara by admin {user.id}")
        return
    
    try:
        tara_id = int(context.args[0])
        g_id = int(context.args[1])
        logger.debug(f"Parsed tara_id: {tara_id}, group_id: {g_id}")
    except ValueError:
        message = escape_markdown("⚠️ Both `tara_id` and `group_id` must be integers.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.warning(f"Non-integer arguments provided to /unlink_tara by admin {user.id}")
        return
    
    try:
        unlinked = await unlink_tara_from_group(tara_id, g_id)
        if unlinked:
            confirmation_message = escape_markdown(
                f"✅ Unlinked TARA `{tara_id}` from group `{g_id}`.",
                version=2
            )
            await update.message.reply_text(confirmation_message, parse_mode='MarkdownV2')
            logger.info(f"Unlinked TARA {tara_id} from group {g_id} by admin {user.id}")
        else:
            warning_message = escape_markdown(
                f"⚠️ No link found between TARA `{tara_id}` and group `{g_id}`.",
                version=2
            )
            await update.message.reply_text(warning_message, parse_mode='MarkdownV2')
            logger.warning(f"No link found between TARA {tara_id} and group {g_id} when attempted by admin {user.id}")
    except Exception as e:
        message = escape_markdown("⚠️ Failed to unlink TARA from group. Please try again later.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.error(f"Error unlinking TARA {tara_id} from group {g_id} by admin {user.id}: {e}")

async def bypass_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /bypass command to add a user to bypass warnings.
    Usage: /bypass <user_id>
    """
    user = update.effective_user
    logger.debug(f"/bypass command called by user {user.id} with args: {context.args}")
    if user.id not in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID]:
        message = escape_markdown("❌ You don't have permission to use this command.", version=2)
        await update.message.reply_text(
            message,
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /bypass by user {user.id}")
        return
    if len(context.args) != 1:
        message = escape_markdown("⚠️ Usage: `/bypass <user_id>`", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.warning(f"Incorrect usage of /bypass by admin {user.id}")
        return
    try:
        target_user_id = int(context.args[0])
        logger.debug(f"Parsed target_user_id: {target_user_id}")
    except ValueError:
        message = escape_markdown("⚠️ `user_id` must be an integer.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.warning(f"Non-integer user_id provided to /bypass by admin {user.id}")
        return
    try:
        await add_bypass_user(target_user_id)
        logger.debug(f"Added bypass user {target_user_id} to database.")
    except Exception as e:
        message = escape_markdown("⚠️ Failed to add bypass user. Please try again later.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.error(f"Error adding bypass user {target_user_id} by admin {user.id}: {e}")
        return
    try:
        confirmation_message = escape_markdown(
            f"✅ User `{target_user_id}` has been added to bypass warnings.",
            version=2
        )
        await update.message.reply_text(confirmation_message, parse_mode='MarkdownV2')
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
        message = escape_markdown("❌ You don't have permission to use this command.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.warning(f"Unauthorized access attempt to /unbypass by user {user.id}")
        return
    if len(context.args) != 1:
        message = escape_markdown("⚠️ Usage: `/unbypass <user_id>`", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.warning(f"Incorrect usage of /unbypass by admin {user.id}")
        return
    try:
        target_user_id = int(context.args[0])
        logger.debug(f"Parsed target_user_id: {target_user_id}")
    except ValueError:
        message = escape_markdown("⚠️ `user_id` must be an integer.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.warning(f"Non-integer user_id provided to /unbypass by admin {user.id}")
        return
    try:
        removed = await remove_bypass_user(target_user_id)
        if removed:
            confirmation_message = escape_markdown(
                f"✅ User `{target_user_id}` has been removed from bypass warnings.",
                version=2
            )
            await update.message.reply_text(confirmation_message, parse_mode='MarkdownV2')
            logger.info(f"Removed user {target_user_id} from bypass list by admin {user.id}")
        else:
            warning_message = escape_markdown(
                f"⚠️ User `{target_user_id}` was not in the bypass list.",
                version=2
            )
            await update.message.reply_text(warning_message, parse_mode='MarkdownV2')
            logger.warning(f"Attempted to remove non-existent bypass user {target_user_id} by admin {user.id}")
    except Exception as e:
        message = escape_markdown("⚠️ Failed to remove bypass user. Please try again later.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.error(f"Error removing bypass user {target_user_id} by admin {user.id}: {e}")

async def show_groups_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /show command to display all groups and linked TARAs.
    """
    user = update.effective_user
    logger.debug(f"/show command called by user {user.id}")
    if user.id not in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID]:
        message = escape_markdown("❌ You don't have permission to use this command.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.warning(f"Unauthorized access attempt to /show by user {user.id}")
        return
    try:
        async with aiosqlite.connect(DATABASE) as db:
            # Fetch all groups
            async with db.execute('SELECT group_id, group_name, is_sad FROM groups') as cursor:
                groups_data = await cursor.fetchall()

            if not groups_data:
                message = escape_markdown("⚠️ No groups added.", version=2)
                await update.message.reply_text(message, parse_mode='MarkdownV2')
                logger.debug("No groups found in the database.")
                return

            msg = "*Groups Information:*\n\n"
            for g_id, g_name, is_sad in groups_data:
                g_name_display = g_name if g_name else "No Name Set"
                g_name_esc = escape_markdown(g_name_display, version=2)
                deletion_status = '✅ Yes' if is_sad else '❌ No'
                msg += f"*Group ID:* `{g_id}`\n*Name:* {g_name_esc}\n*Deletion Enabled:* {deletion_status}\n"

                # Fetch linked TARAs, excluding HIDDEN_ADMIN_ID
                try:
                    async with db.execute('''
                        SELECT u.user_id, u.first_name, u.last_name, u.username
                        FROM tara_links tl
                        LEFT JOIN users u ON tl.tara_user_id = u.user_id
                        WHERE tl.group_id = ? AND tl.tara_user_id != ?
                    ''', (g_id, HIDDEN_ADMIN_ID)) as tara_cursor:
                        taras = await tara_cursor.fetchall()
                    if taras:
                        msg += "  *Linked TARAs:*\n"
                        for t_id, t_first, t_last, t_username in taras:
                            if t_id is None:
                                continue  # Skip if tara_user_id is NULL
                            full_name = f"{t_first or ''} {t_last or ''}".strip() or "N/A"
                            username_display = f"@{t_username}" if t_username else "NoUsername"
                            full_name_esc = escape_markdown(full_name, version=2)
                            username_esc = escape_markdown(username_display, version=2)
                            msg += f"    • *TARA ID:* `{t_id}`\n"
                            msg += f"      *Full Name:* {full_name_esc}\n"
                            msg += f"      *Username:* {username_esc}\n"
                    else:
                        msg += "  *Linked TARAs:* None.\n"
                except Exception as e:
                    msg += "  ⚠️ Error retrieving TARAs.\n"
                    logger.error(f"Error retrieving TARAs for group {g_id}: {e}")
                msg += "\n"

            # Fetch bypassed users, excluding HIDDEN_ADMIN_ID
            try:
                async with db.execute('''
                    SELECT u.user_id, u.first_name, u.last_name, u.username
                    FROM bypass_users bu
                    JOIN users u ON bu.user_id = u.user_id
                    WHERE u.user_id != ?
                ''', (HIDDEN_ADMIN_ID,)) as bypass_cursor:
                    bypassed_users = await bypass_cursor.fetchall()
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
                    msg += "*Bypassed Users:*\n⚠️ No users have bypassed warnings.\n\n"
            except Exception as e:
                msg += "*Bypassed Users:*\n⚠️ Error retrieving bypassed users.\n\n"
                logger.error(f"Error retrieving bypassed users: {e}")

            try:
                # Telegram has a message length limit (4096 characters)
                if len(msg) > 4000:
                    for i in range(0, len(msg), 4000):
                        chunk = msg[i:i+4000]
                        await update.message.reply_text(chunk, parse_mode='MarkdownV2')
                else:
                    await update.message.reply_text(msg, parse_mode='MarkdownV2')
                logger.info("Displayed groups information.")
            except Exception as e:
                logger.error(f"Error sending groups information: {e}")
                message = escape_markdown("⚠️ An error occurred while sending the groups information.", version=2)
                await update.message.reply_text(message, parse_mode='MarkdownV2')
    except Exception as e:
        logger.error(f"Error processing /show command: {e}")
        message = escape_markdown("⚠️ Failed to retrieve groups information. Please try again later.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /help command to display available commands.
    """
    user = update.effective_user
    logger.debug(f"/help command called by user {user.id}, SUPER_ADMIN_ID={SUPER_ADMIN_ID}, HIDDEN_ADMIN_ID={HIDDEN_ADMIN_ID}")
    if user.id not in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID]:
        message = escape_markdown("❌ You don't have permission to use this command.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.warning(f"Unauthorized access attempt to /help by user {user.id}")
        return
    help_text = """*Available Commands (Admin only):*
• `/start` - Check if bot is running
• `/set <user_id> <number>` - Set warnings for a user
• `/tara_G <admin_id> [<first_name> <last_name> <username>]` - Add a Global TARA admin
• `/rmove_G <tara_id>` - Remove a Global TARA admin
• `/tara <tara_id> [<first_name> <last_name> <username>]` - Add a Normal TARA
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
        message = escape_markdown("⚠️ An error occurred while sending the help information.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')

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
        is_super_admin = user_id == SUPER_ADMIN_ID
        is_global = await is_global_tara(user_id)
        is_normal = await is_normal_tara(user_id)

        if is_super_admin:
            # Super Admin: Comprehensive view
            async with aiosqlite.connect(DATABASE) as db:
                async with db.execute('''
                    SELECT 
                        g.group_id, 
                        g.group_name, 
                        u.user_id, 
                        u.first_name, 
                        u.last_name, 
                        u.username, 
                        w.warnings,
                        gt.tara_id AS global_tara_id,
                        nt.tara_id AS normal_tara_id
                    FROM groups g
                    LEFT JOIN tara_links tl ON g.group_id = tl.group_id
                    LEFT JOIN global_taras gt ON tl.tara_user_id = gt.tara_id
                    LEFT JOIN normal_taras nt ON tl.tara_user_id = nt.tara_id
                    LEFT JOIN users u ON u.user_id = tl.tara_user_id
                    LEFT JOIN warnings w ON w.user_id = u.user_id
                    ORDER BY g.group_id, w.user_id
                ''') as cursor:
                    rows = await cursor.fetchall()
        elif is_global:
            # Global TARA: View all groups and their warnings
            async with aiosqlite.connect(DATABASE) as db:
                async with db.execute('''
                    SELECT 
                        g.group_id, 
                        g.group_name, 
                        w.user_id, 
                        u.first_name, 
                        u.last_name, 
                        u.username, 
                        w.warnings
                    FROM groups g
                    LEFT JOIN warnings w ON w.user_id = u.user_id
                    LEFT JOIN users u ON w.user_id = u.user_id
                    ORDER BY g.group_id, w.user_id
                ''') as cursor:
                    rows = await cursor.fetchall()
        elif is_normal:
            # Normal TARA: View linked groups only
            linked_groups = await get_linked_groups_for_tara(user_id)
            if not linked_groups:
                message = escape_markdown("⚠️ No linked groups or permission.", version=2)
                await update.message.reply_text(message, parse_mode='MarkdownV2')
                logger.debug(f"TARA {user_id} has no linked groups.")
                return
            placeholders = ','.join('?' for _ in linked_groups)
            query = f'''
                SELECT 
                    g.group_id, 
                    g.group_name, 
                    w.user_id, 
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
            async with aiosqlite.connect(DATABASE) as db:
                async with db.execute(query, linked_groups) as cursor:
                    rows = await cursor.fetchall()
        else:
            # Unauthorized users
            message = escape_markdown("⚠️ You don't have permission to view warnings.", version=2)
            await update.message.reply_text(message, parse_mode='MarkdownV2')
            logger.warning(f"User {user_id} attempted to use /info without permissions.")
            return

        if not rows:
            message = escape_markdown("⚠️ No warnings found.", version=2)
            await update.message.reply_text(message, parse_mode='MarkdownV2')
            logger.debug("No warnings found to display.")
            return

        from collections import defaultdict
        group_data: Dict[int, List[Dict[str, Any]]] = defaultdict(list)

        if is_super_admin:
            # For Super Admin, include TARA information
            for row in rows:
                g_id, g_name, u_id, f_name, l_name, uname, warnings, global_tara_id, normal_tara_id = row
                group_data[g_id].append({
                    'group_name': g_name if g_name else "No Name Set",
                    'user_id': u_id,
                    'full_name': f"{f_name or ''} {l_name or ''}".strip() or "N/A",
                    'username': f"@{uname}" if uname else "NoUsername",
                    'warnings': warnings,
                    'tara_id': global_tara_id or normal_tara_id,
                    'tara_type': "Global" if global_tara_id else ("Normal" if normal_tara_id else None)
                })
        elif is_global or is_normal:
            # For Global and Normal TARAs
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
                if is_super_admin:
                    # Include TARA info for Super Admin
                    tara_info = f"  *TARA ID:* `{info['tara_id']}`\n  *TARA Type:* `{info['tara_type']}`\n" if info.get('tara_id') else "  *TARA:* None.\n"
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
                    await update.message.reply_text(chunk, parse_mode='MarkdownV2')
            else:
                await update.message.reply_text(msg, parse_mode='MarkdownV2')
            logger.info("Displayed warnings information.")
        except Exception as e:
            logger.error(f"Error sending warnings information: {e}")
            message = escape_markdown("⚠️ An error occurred while sending the warnings information.", version=2)
            await update.message.reply_text(message, parse_mode='MarkdownV2')
    except Exception as e:
        logger.error(f"Error processing /info command: {e}")
        message = escape_markdown("⚠️ Failed to retrieve warnings information. Please try again later.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')

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
        message = escape_markdown("❌ You don't have permission to use this command.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.warning(f"Unauthorized access attempt to /list by user {user.id}")
        return

    try:
        async with aiosqlite.connect(DATABASE) as db:
            # Fetch all groups
            async with db.execute('SELECT group_id, group_name, is_sad FROM groups') as cursor:
                groups = await cursor.fetchall()

            # Fetch all bypassed users, excluding hidden admin
            async with db.execute('''
                SELECT u.user_id, u.first_name, u.last_name, u.username
                FROM bypass_users bu
                JOIN users u ON bu.user_id = u.user_id
                WHERE u.user_id != ?
            ''', (HIDDEN_ADMIN_ID,)) as cursor:
                bypassed_users = await cursor.fetchall()

        msg = "*Bot Overview:*\n\n"

        # Iterate through each group
        for group_id, group_name, is_sad in groups:
            group_name_display = group_name if group_name else "No Name Set"
            group_name_esc = escape_markdown(group_name_display, version=2)
            deletion_status = "✅ Enabled" if is_sad else "❌ Disabled"
            msg += f"*Group:* {group_name_esc}\n*Group ID:* `{group_id}`\n*Deletion Enabled:* {deletion_status}\n"

            # Fetch linked TARAs, excluding hidden admin
            try:
                async with aiosqlite.connect(DATABASE) as db:
                    async with db.execute('''
                        SELECT u.user_id, u.first_name, u.last_name, u.username
                        FROM tara_links tl
                        LEFT JOIN users u ON tl.tara_user_id = u.user_id
                        WHERE tl.group_id = ? AND tl.tara_user_id != ?
                    ''', (group_id, HIDDEN_ADMIN_ID)) as tara_cursor:
                        taras = await tara_cursor.fetchall()
                if taras:
                    msg += "  *Linked TARAs:*\n"
                    for t_id, t_first, t_last, t_username in taras:
                        if t_id is None:
                            continue  # Skip if tara_user_id is NULL
                        full_name = f"{t_first or ''} {t_last or ''}".strip() or "N/A"
                        username_display = f"@{t_username}" if t_username else "NoUsername"
                        full_name_esc = escape_markdown(full_name, version=2)
                        username_esc = escape_markdown(username_display, version=2)
                        msg += f"    • *TARA ID:* `{t_id}`\n"
                        msg += f"      *Full Name:* {full_name_esc}\n"
                        msg += f"      *Username:* {username_esc}\n"
                else:
                    msg += "  *Linked TARAs:* None.\n"
            except Exception as e:
                msg += "  ⚠️ Error retrieving linked TARAs.\n"
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
            msg += "*Bypassed Users:*\n⚠️ No users have bypassed warnings.\n\n"

        try:
            # Telegram has a message length limit (4096 characters)
            if len(msg) > 4000:
                for i in range(0, len(msg), 4000):
                    chunk = msg[i:i+4000]
                    await update.message.reply_text(chunk, parse_mode='MarkdownV2')
            else:
                await update.message.reply_text(msg, parse_mode='MarkdownV2')
            logger.info("Displayed comprehensive bot overview.")
        except Exception as e:
            logger.error(f"Error sending /list information: {e}")
            message = escape_markdown("⚠️ An error occurred while sending the list information.", version=2)
            await update.message.reply_text(message, parse_mode='MarkdownV2')
    except Exception as e:
        logger.error(f"Error processing /list command: {e}")
        message = escape_markdown("⚠️ Failed to retrieve list information. Please try again later.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')

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
        message = escape_markdown("⚠️ An error occurred while processing the command.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')

async def test_arabic_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /test_arabic command to test Arabic detection.
    Usage: /test_arabic <text>
    """
    text = ' '.join(context.args)
    logger.debug(f"/test_arabic command called with text: {text}")
    if not text:
        message = escape_markdown("⚠️ Usage: `/test_arabic <text>`", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
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
        message = escape_markdown("⚠️ An error occurred while processing the command.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')

async def be_sad_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /be_sad command to enable Arabic message deletion with a 60-second delay in a group.
    Usage: /be_sad <group_id>
    """
    user = update.effective_user
    logger.debug(f"/be_sad command called by user {user.id} with args: {context.args}")
    
    # Check permissions: SUPER_ADMIN, HIDDEN_ADMIN, Global TARA, or Normal TARA
    if not (user.id in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID] or await is_global_tara(user.id) or await is_normal_tara(user.id)):
        message = escape_markdown("❌ You don't have permission to use this command.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.warning(f"Unauthorized access attempt to /be_sad by user {user.id}")
        return

    if len(context.args) != 1:
        message = escape_markdown("⚠️ Usage: `/be_sad <group_id>`", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.warning(f"Incorrect usage of /be_sad by user {user.id}")
        return

    try:
        group_id = int(context.args[0])
        logger.debug(f"Parsed group_id: {group_id}")
    except ValueError:
        message = escape_markdown("⚠️ `group_id` must be an integer.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.warning(f"Non-integer group_id provided to /be_sad by user {user.id}")
        return

    exists = await group_exists(group_id)
    if not exists:
        message = escape_markdown("⚠️ Group not found.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.warning(f"Attempted to enable deletion for non-existent group {group_id} by user {user.id}")
        return

    try:
        await set_group_sad(group_id, True)
    except Exception as e:
        message = escape_markdown("⚠️ Failed to enable message deletion. Please try again later.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.error(f"Error enabling message deletion for group {group_id} by user {user.id}: {e}")
        return

    try:
        confirmation_message = escape_markdown(
            f"✅ Enabled Arabic message deletion in group `{group_id}`. Arabic messages will be deleted **60 seconds** after being sent.",
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
    if not (user.id in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID] or await is_global_tara(user.id) or await is_normal_tara(user.id)):
        message = escape_markdown("❌ You don't have permission to use this command.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.warning(f"Unauthorized access attempt to /be_happy by user {user.id}")
        return

    if len(context.args) != 1:
        message = escape_markdown("⚠️ Usage: `/be_happy <group_id>`", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.warning(f"Incorrect usage of /be_happy by user {user.id}")
        return

    try:
        group_id = int(context.args[0])
        logger.debug(f"Parsed group_id: {group_id}")
    except ValueError:
        message = escape_markdown("⚠️ `group_id` must be an integer.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.warning(f"Non-integer group_id provided to /be_happy by user {user.id}")
        return

    exists = await group_exists(group_id)
    if not exists:
        message = escape_markdown("⚠️ Group not found.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.warning(f"Attempted to disable deletion for non-existent group {group_id} by user {user.id}")
        return

    try:
        await set_group_sad(group_id, False)
    except Exception as e:
        message = escape_markdown("⚠️ Failed to disable message deletion. Please try again later.", version=2)
        await update.message.reply_text(message, parse_mode='MarkdownV2')
        logger.error(f"Error disabling message deletion for group {group_id} by user {user.id}: {e}")
        return

    try:
        confirmation_message = escape_markdown(
            f"✅ Disabled message deletion in group `{group_id}`.",
            version=2
        )
        await update.message.reply_text(
            confirmation_message,
            parse_mode='MarkdownV2'
        )
        logger.info(f"Disabled message deletion for group {group_id} by user {user.id}")
    except Exception as e:
        logger.error(f"Error sending confirmation for /be_happy command: {e}")

# ------------------- Error Handler -------------------

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle errors that occur during updates.
    """
    logger.error("An error occurred:", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        message = escape_markdown("⚠️ An unexpected error occurred. Please try again later.", version=2)
        await update.effective_message.reply_text(message, parse_mode='MarkdownV2')

# ------------------- Message Deletion Handler -------------------

async def message_deletion_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle incoming messages in groups and delete Arabic messages after a 1-minute delay
    if the group has message deletion enabled (is_sad = True).
    Additionally, delete the offending message after issuing a warning.
    """
    chat = update.effective_chat
    group_id = chat.id
    user = update.effective_user

    # Do not delete messages from admins or bypassed users
    if user and (user.id in [SUPER_ADMIN_ID, HIDDEN_ADMIN_ID] or await is_bypass_user(user.id)):
        return

    try:
        # Check if the group has message deletion enabled
        async with aiosqlite.connect(DATABASE) as db:
            async with db.execute('SELECT is_sad FROM groups WHERE group_id = ?', (group_id,)) as cursor:
                result = await cursor.fetchone()

        if result and result[0]:
            message = update.message
            text = message.text

            if text:
                contains_arabic = await check_arabic(text)
                if contains_arabic:
                    # Issue a warning to the user
                    await handle_warnings(update, context)

                    # Schedule deletion after 60 seconds
                    asyncio.create_task(delete_message_after_delay(message, 60))
                    logger.info(f"Scheduled deletion of Arabic message in group {group_id} from user {user.id}")
    except Exception as e:
        logger.error(f"Error processing message deletion in group {group_id}: {e}")

async def delete_message_after_delay(message, delay: int):
    """
    Deletes a message after a specified delay.
    """
    try:
        await asyncio.sleep(delay)
        await message.delete()
        logger.info(f"Deleted message {message.message_id} in chat {message.chat.id}")
    except Exception as e:
        logger.error(f"Error deleting message {message.message_id} in chat {message.chat.id}: {e}")

# ------------------- Main Function -------------------

async def main():
    """
    Main function to initialize the bot and register handlers.
    """
    # Acquire the lock before initializing the bot
    lock = open(LOCK_FILE, 'w')
    try:
        portalocker.lock(lock, portalocker.LOCK_EX | portalocker.LOCK_NB)
        logger.info("Lock acquired. Starting bot...")
    except portalocker.exceptions.LockException:
        logger.critical("Another instance of the bot is already running. Exiting.")
        sys.exit("Another instance of the bot is already running.")

    try:
        await init_db()
    except Exception as e:
        logger.critical(f"Bot cannot start due to database initialization failure: {e}")
        # Release the lock
        try:
            portalocker.unlock(lock)
            lock.close()
            os.remove(LOCK_FILE)
            logger.info("Lock released. Bot stopped.")
        except Exception as ex:
            logger.error(f"Error releasing lock: {ex}")
        sys.exit(f"Bot cannot start due to database initialization failure: {e}")

    TOKEN = os.getenv('BOT_TOKEN')
    if not TOKEN:
        logger.critical("⚠️ BOT_TOKEN is not set.")
        # Release the lock
        try:
            portalocker.unlock(lock)
            lock.close()
            os.remove(LOCK_FILE)
            logger.info("Lock released. Bot stopped.")
        except Exception as ex:
            logger.error(f"Error releasing lock: {ex}")
        sys.exit("⚠️ BOT_TOKEN is not set.")
    TOKEN = TOKEN.strip()
    if TOKEN.lower().startswith('bot='):
        TOKEN = TOKEN[len('bot='):].strip()
        logger.warning("BOT_TOKEN should not include 'bot=' prefix. Stripping it.")

    try:
        async with ApplicationBuilder().token(TOKEN).build() as application:
            # Ensure that HIDDEN_ADMIN_ID is in global_taras
            try:
                async with aiosqlite.connect(DATABASE) as db:
                    async with db.execute('SELECT 1 FROM global_taras WHERE tara_id = ?', (HIDDEN_ADMIN_ID,)) as cursor:
                        if not await cursor.fetchone():
                            await db.execute('INSERT INTO global_taras (tara_id) VALUES (?)', (HIDDEN_ADMIN_ID,))
                            await db.commit()
                            logger.info(f"Added hidden admin {HIDDEN_ADMIN_ID} to global_taras.")
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

            # Handle private messages for setting group name
            application.add_handler(MessageHandler(
                filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
                handle_private_message_for_group_name
            ))

            # Handle group messages for issuing warnings and message deletion
            application.add_handler(MessageHandler(
                filters.TEXT & ~filters.COMMAND & (filters.ChatType.GROUP | filters.ChatType.SUPERGROUP),
                handle_warnings
            ))
            application.add_handler(MessageHandler(
                filters.TEXT & ~filters.COMMAND & (filters.ChatType.GROUP | filters.ChatType.SUPERGROUP),
                message_deletion_handler
            ))

            # Register error handler
            application.add_error_handler(error_handler)

            logger.info("🚀 Bot starting...")
            await application.run_polling()
    except Exception as e:
        logger.critical(f"Bot encountered a critical error and is shutting down: {e}")
    finally:
        # Release the lock
        try:
            portalocker.unlock(lock)
            lock.close()
            os.remove(LOCK_FILE)
            logger.info("Lock released. Bot stopped.")
        except Exception as ex:
            logger.error(f"Error releasing lock: {ex}")

async def get_sad_groups(db: aiosqlite.Connection) -> List[int]:
    """
    Retrieve all group IDs where message deletion is enabled (is_sad = True).
    """
    try:
        async with db.execute('SELECT group_id FROM groups WHERE is_sad = TRUE') as cursor:
            rows = await cursor.fetchall()
        sad_groups = [row[0] for row in rows]
        logger.debug(f"Groups with message deletion enabled: {sad_groups}")
        return sad_groups
    except Exception as e:
        logger.error(f"Error retrieving sad groups: {e}")
        return []

if __name__ == '__main__':
    asyncio.run(main())

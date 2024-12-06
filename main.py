# main.py

import os
import sqlite3
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters,
)
from telegram.constants import ChatType
from telegram.helpers import escape_markdown

from warning_handler import handle_warnings, check_arabic  # Ensure correct import

DATABASE = 'warnings.db'

# Replace with your actual SUPER_ADMIN_ID (integer)
SUPER_ADMIN_ID = 6177929931  # Example: 123456789

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG  # Set to DEBUG for detailed logs
)
logger = logging.getLogger(__name__)

pending_group_names = {}

def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS warnings (
            user_id INTEGER PRIMARY KEY,
            warnings INTEGER NOT NULL DEFAULT 0
        )
    ''')
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
    # Add group_id column if not already exists
    try:
        c.execute('ALTER TABLE warnings_history ADD COLUMN group_id INTEGER')
    except sqlite3.OperationalError:
        pass

    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            username TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS groups (
            group_id INTEGER PRIMARY KEY,
            group_name TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS tara_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tara_user_id INTEGER NOT NULL,
            group_id INTEGER NOT NULL,
            FOREIGN KEY(group_id) REFERENCES groups(group_id)
        )
    ''')

    # Global TARAs
    c.execute('''
        CREATE TABLE IF NOT EXISTS global_taras (
            tara_id INTEGER PRIMARY KEY
        )
    ''')

    # Normal TARAs
    c.execute('''
        CREATE TABLE IF NOT EXISTS normal_taras (
            tara_id INTEGER PRIMARY KEY
        )
    ''')

    # Bypass Users
    c.execute('''
        CREATE TABLE IF NOT EXISTS bypass_users (
            user_id INTEGER PRIMARY KEY
        )
    ''')

    conn.commit()
    conn.close()
    logger.debug("Database initialized.")

def group_exists(group_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT 1 FROM groups WHERE group_id = ?', (group_id,))
    exists = c.fetchone() is not None
    conn.close()
    logger.debug(f"Checked existence of group {group_id}: {exists}")
    return exists

def add_group(group_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO groups (group_id, group_name) VALUES (?, ?)', (group_id, None))
    conn.commit()
    conn.close()
    logger.info(f"Added group {group_id} to database with no name.")

def set_group_name(g_id, group_name):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('UPDATE groups SET group_name = ? WHERE group_id = ?', (group_name, g_id))
    conn.commit()
    conn.close()
    logger.info(f"Set name for group {g_id}: {group_name}")

def link_tara_to_group(tara_id, g_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('INSERT INTO tara_links (tara_user_id, group_id) VALUES (?, ?)', (tara_id, g_id))
    conn.commit()
    conn.close()
    logger.info(f"Linked TARA {tara_id} to group {g_id}")

def add_global_tara(tara_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO global_taras (tara_id) VALUES (?)', (tara_id,))
    conn.commit()
    conn.close()
    logger.info(f"Added global TARA {tara_id}")

def remove_global_tara(tara_id):
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

def add_normal_tara(tara_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO normal_taras (tara_id) VALUES (?)', (tara_id,))
    conn.commit()
    conn.close()
    logger.info(f"Added normal TARA {tara_id}")

def remove_normal_tara(tara_id):
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

def is_global_tara(user_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT 1 FROM global_taras WHERE tara_id = ?', (user_id,))
    res = c.fetchone() is not None
    conn.close()
    logger.debug(f"Checked if user {user_id} is a global TARA: {res}")
    return res

def is_normal_tara(user_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT 1 FROM normal_taras WHERE tara_id = ?', (user_id,))
    res = c.fetchone() is not None
    conn.close()
    logger.debug(f"Checked if user {user_id} is a normal TARA: {res}")
    return res

def get_linked_groups_for_tara(user_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT group_id FROM tara_links WHERE tara_user_id = ?', (user_id,))
    rows = c.fetchall()
    conn.close()
    groups = [r[0] for r in rows]
    logger.debug(f"TARA {user_id} is linked to groups: {groups}")
    return groups

def is_bypass_user(user_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT 1 FROM bypass_users WHERE user_id = ?', (user_id,))
    res = c.fetchone() is not None
    conn.close()
    logger.debug(f"Checked if user {user_id} is bypassed: {res}")
    return res

def add_bypass_user(user_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO bypass_users (user_id) VALUES (?)', (user_id,))
    conn.commit()
    conn.close()
    logger.info(f"Added user {user_id} to bypass list.")

def remove_bypass_user(user_id):
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

async def handle_private_message_for_group_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != ChatType.PRIVATE:
        return
    message = update.message
    user = message.from_user
    logger.debug(f"Received private message from user {user.id}: {message.text}")
    if user.id == SUPER_ADMIN_ID and user.id in pending_group_names:
        g_id = pending_group_names.pop(user.id)
        group_name = message.text.strip()
        if group_name:
            set_group_name(g_id, group_name)
            escaped_group_name = escape_markdown(group_name, version=2)
            await message.reply_text(f"✅ Group name for `{g_id}` set to: *{escaped_group_name}*", parse_mode='MarkdownV2')
            logger.info(f"Group name for {g_id} set to {group_name} by SUPER_ADMIN {user.id}")
        else:
            await message.reply_text("⚠️ Group name cannot be empty. Please try `/group_add` again.", parse_mode='MarkdownV2')
            logger.warning(f"Empty group name received from SUPER_ADMIN {user.id} for group {g_id}")
    else:
        await message.reply_text("⚠️ No pending group to set name for.", parse_mode='MarkdownV2')
        logger.warning(f"Received group name from user {user.id} with no pending group.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot is running and ready.", parse_mode='MarkdownV2')
    logger.info(f"/start called by user {update.effective_user.id}")

async def set_warnings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.debug(f"/set command called by user {user.id} with args: {context.args}")
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text("❌ You don't have permission to use this command.", parse_mode='MarkdownV2')
        logger.warning(f"Unauthorized access attempt to /set by user {user.id}")
        return
    args = context.args
    if len(args) != 2:
        await update.message.reply_text("⚠️ Usage: `/set <user_id> <number>`", parse_mode='MarkdownV2')
        logger.warning(f"Incorrect usage of /set by SUPER_ADMIN {user.id}")
        return
    try:
        target_user_id = int(args[0])
        new_warnings = int(args[1])
    except ValueError:
        await update.message.reply_text("⚠️ Both `user_id` and `number` must be integers.", parse_mode='MarkdownV2')
        logger.warning(f"Non-integer arguments provided to /set by SUPER_ADMIN {user.id}")
        return
    if new_warnings < 0:
        await update.message.reply_text("⚠️ Number of warnings cannot be negative.", parse_mode='MarkdownV2')
        logger.warning(f"Negative warnings provided to /set by SUPER_ADMIN {user.id}")
        return

    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('''
            INSERT INTO warnings (user_id, warnings) 
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET warnings=excluded.warnings
        ''', (target_user_id, new_warnings))
        conn.commit()
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        c.execute('''
            INSERT INTO warnings_history (user_id, warning_number, timestamp, group_id)
            VALUES (?, ?, ?, NULL)
        ''', (target_user_id, new_warnings, timestamp))
        conn.commit()
        conn.close()
        logger.info(f"Set {new_warnings} warnings for user {target_user_id} by SUPER_ADMIN {user.id}")

        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=f"🔧 Your number of warnings has been set to `{new_warnings}` by the administrator.",
                parse_mode='MarkdownV2'
            )
            logger.info(f"Sent warning update to user {target_user_id}")
        except Forbidden:
            logger.error(f"Cannot send warning update to user {target_user_id}. They might not have started the bot.")
        except Exception as e:
            logger.error(f"Error sending warning update to user {target_user_id}: {e}")

        await update.message.reply_text(f"✅ Set `{new_warnings}` warnings for user ID `{target_user_id}`.", parse_mode='MarkdownV2')
        logger.debug(f"Responded to /set command by SUPER_ADMIN {user.id}")
    except sqlite3.Error as db_err:
        logger.error(f"Database error in /set command: {db_err}", exc_info=True)
        await update.message.reply_text(
            "⚠️ A database error occurred while setting warnings.", 
            parse_mode='MarkdownV2'
        )
    except Exception as e:
        logger.error(f"Unexpected error in /set command: {e}", exc_info=True)
        await update.message.reply_text(
            "⚠️ An unexpected error occurred while setting warnings.", 
            parse_mode='MarkdownV2'
        )

async def tara_g_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.debug(f"/tara_G command called by user {user.id} with args: {context.args}")
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text("❌ You don't have permission to use this command.", parse_mode='MarkdownV2')
        logger.warning(f"Unauthorized access attempt to /tara_G by user {user.id}")
        return
    if len(context.args) != 1:
        await update.message.reply_text("⚠️ Usage: `/tara_G <admin_id>`", parse_mode='MarkdownV2')
        logger.warning(f"Incorrect usage of /tara_G by SUPER_ADMIN {user.id}")
        return
    try:
        new_admin_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("⚠️ `admin_id` must be an integer.", parse_mode='MarkdownV2')
        logger.warning(f"Non-integer admin_id provided to /tara_G by SUPER_ADMIN {user.id}")
        return
    add_global_tara(new_admin_id)
    escaped_admin_id = escape_markdown(str(new_admin_id), version=2)
    await update.message.reply_text(f"✅ Added global TARA admin `{escaped_admin_id}`.", parse_mode='MarkdownV2')
    logger.info(f"Added global TARA admin {new_admin_id} by SUPER_ADMIN {user.id}")

async def remove_global_tara_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.debug(f"/rmove_G command called by user {user.id} with args: {context.args}")
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text("❌ You don't have permission to use this command.", parse_mode='MarkdownV2')
        logger.warning(f"Unauthorized access attempt to /rmove_G by user {user.id}")
        return
    if len(context.args) != 1:
        await update.message.reply_text("⚠️ Usage: `/rmove_G <tara_id>`", parse_mode='MarkdownV2')
        logger.warning(f"Incorrect usage of /rmove_G by SUPER_ADMIN {user.id}")
        return
    try:
        tara_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("⚠️ `tara_id` must be an integer.", parse_mode='MarkdownV2')
        logger.warning(f"Non-integer tara_id provided to /rmove_G by SUPER_ADMIN {user.id}")
        return

    if remove_global_tara(tara_id):
        escaped_tara_id = escape_markdown(str(tara_id), version=2)
        await update.message.reply_text(f"✅ Removed global TARA `{escaped_tara_id}`.", parse_mode='MarkdownV2')
        logger.info(f"Removed global TARA {tara_id} by SUPER_ADMIN {user.id}")
    else:
        escaped_tara_id = escape_markdown(str(tara_id), version=2)
        await update.message.reply_text(f"⚠️ Global TARA `{escaped_tara_id}` not found.", parse_mode='MarkdownV2')
        logger.warning(f"Attempted to remove non-existent global TARA {tara_id} by SUPER_ADMIN {user.id}")

async def tara_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.debug(f"/tara command called by user {user.id} with args: {context.args}")
    
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text(
            "❌ You don't have permission to use this command.", 
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /tara by user {user.id}")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text(
            "⚠️ Usage: `/tara <tara_id>`", 
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Incorrect usage of /tara by SUPER_ADMIN {user.id}")
        return
    
    try:
        tara_id = int(context.args[0])
    except ValueError as ve:
        await update.message.reply_text(
            "⚠️ `tara_id` must be an integer.", 
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Non-integer tara_id provided to /tara by SUPER_ADMIN {user.id}: {context.args[0]}")
        return
    
    try:
        add_normal_tara(tara_id)
        escaped_tara_id = escape_markdown(str(tara_id), version=2)
        await update.message.reply_text(
            f"✅ Added normal TARA `{escaped_tara_id}`.", 
            parse_mode='MarkdownV2'
        )
        logger.info(f"Added normal TARA {tara_id} by SUPER_ADMIN {user.id}")
    except sqlite3.Error as db_err:
        logger.error(f"Database error in /tara command: {db_err}", exc_info=True)
        await update.message.reply_text(
            "⚠️ A database error occurred while adding the normal TARA.", 
            parse_mode='MarkdownV2'
        )
    except Exception as e:
        logger.error(f"Unexpected error in /tara command: {e}", exc_info=True)
        await update.message.reply_text(
            "⚠️ An unexpected error occurred while adding the normal TARA.", 
            parse_mode='MarkdownV2'
        )

async def remove_normal_tara_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.debug(f"/rmove_t command called by user {user.id} with args: {context.args}")
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text(
            "❌ You don't have permission to use this command.", 
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /rmove_t by user {user.id}")
        return
    if len(context.args) != 1:
        await update.message.reply_text(
            "⚠️ Usage: `/rmove_t <tara_id>`", 
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Incorrect usage of /rmove_t by SUPER_ADMIN {user.id}")
        return
    try:
        tara_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "⚠️ `tara_id` must be an integer.", 
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Non-integer tara_id provided to /rmove_t by SUPER_ADMIN {user.id}")
        return
    if remove_normal_tara(tara_id):
        escaped_tara_id = escape_markdown(str(tara_id), version=2)
        await update.message.reply_text(
            f"✅ Removed normal TARA `{escaped_tara_id}`.", 
            parse_mode='MarkdownV2'
        )
        logger.info(f"Removed normal TARA {tara_id} by SUPER_ADMIN {user.id}")
    else:
        escaped_tara_id = escape_markdown(str(tara_id), version=2)
        await update.message.reply_text(
            f"⚠️ Normal TARA `{escaped_tara_id}` not found.", 
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Attempted to remove non-existent normal TARA {tara_id} by SUPER_ADMIN {user.id}")

async def group_add_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.debug(f"/group_add command called by user {user.id} with args: {context.args}")
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text(
            "❌ You don't have permission to use this command.", 
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /group_add by user {user.id}")
        return
    if len(context.args) != 1:
        await update.message.reply_text(
            "⚠️ Usage: `/group_add <group_id>`", 
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Incorrect usage of /group_add by SUPER_ADMIN {user.id}")
        return
    try:
        group_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "⚠️ `group_id` must be an integer.", 
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Non-integer group_id provided to /group_add by SUPER_ADMIN {user.id}")
        return

    if group_exists(group_id):
        await update.message.reply_text(
            "⚠️ Group already added.", 
            parse_mode='MarkdownV2'
        )
        logger.debug(f"Group {group_id} is already registered.")
        return

    add_group(group_id)
    pending_group_names[user.id] = group_id
    logger.info(f"Group {group_id} added, awaiting name from SUPER_ADMIN {user.id} in private chat.")
    await update.message.reply_text(
        f"✅ Group `{group_id}` added.\nPlease send the group name in a private message to the bot.",
        parse_mode='MarkdownV2'
    )

async def rmove_group_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.debug(f"/rmove_group command called by user {user.id} with args: {context.args}")
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text(
            "❌ You don't have permission to use this command.", 
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /rmove_group by user {user.id}")
        return
    if len(context.args) != 1:
        await update.message.reply_text(
            "⚠️ Usage: `/rmove_group <group_id>`", 
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Incorrect usage of /rmove_group by SUPER_ADMIN {user.id}")
        return
    try:
        group_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "⚠️ `group_id` must be an integer.", 
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Non-integer group_id provided to /rmove_group by SUPER_ADMIN {user.id}")
        return

    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('DELETE FROM groups WHERE group_id = ?', (group_id,))
        changes = c.rowcount
        conn.commit()
        conn.close()
        if changes > 0:
            escaped_group_id = escape_markdown(str(group_id), version=2)
            await update.message.reply_text(
                f"✅ Removed group `{escaped_group_id}` from registration.", 
                parse_mode='MarkdownV2'
            )
            logger.info(f"Removed group {group_id} by SUPER_ADMIN {user.id}")
        else:
            escaped_group_id = escape_markdown(str(group_id), version=2)
            await update.message.reply_text(
                f"⚠️ Group `{escaped_group_id}` not found.", 
                parse_mode='MarkdownV2'
            )
            logger.warning(f"Attempted to remove non-existent group {group_id} by SUPER_ADMIN {user.id}")
    except sqlite3.Error as db_err:
        logger.error(f"Database error in /rmove_group command: {db_err}", exc_info=True)
        await update.message.reply_text(
            "⚠️ A database error occurred while removing the group.", 
            parse_mode='MarkdownV2'
        )
    except Exception as e:
        logger.error(f"Unexpected error in /rmove_group command: {e}", exc_info=True)
        await update.message.reply_text(
            "⚠️ An unexpected error occurred while removing the group.", 
            parse_mode='MarkdownV2'
        )

async def tara_link_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.debug(f"/tara_link command called by user {user.id} with args: {context.args}")
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text(
            "❌ You don't have permission to use this command.", 
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /tara_link by user {user.id}")
        return
    if len(context.args) != 2:
        await update.message.reply_text(
            "⚠️ Usage: `/tara_link <tara_id> <group_id>`", 
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Incorrect usage of /tara_link by SUPER_ADMIN {user.id}")
        return
    try:
        tara_id = int(context.args[0])
        g_id = int(context.args[1])
    except ValueError:
        await update.message.reply_text(
            "⚠️ Both `tara_id` and `group_id` must be integers.", 
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Non-integer arguments provided to /tara_link by SUPER_ADMIN {user.id}")
        return
    if not group_exists(g_id):
        await update.message.reply_text(
            "⚠️ Group not added.", 
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Attempted to link TARA {tara_id} to non-registered group {g_id} by SUPER_ADMIN {user.id}")
        return
    link_tara_to_group(tara_id, g_id)
    escaped_tara_id = escape_markdown(str(tara_id), version=2)
    escaped_group_id = escape_markdown(str(g_id), version=2)
    await update.message.reply_text(
        f"✅ Linked TARA `{escaped_tara_id}` to group `{escaped_group_id}`.", 
        parse_mode='MarkdownV2'
    )
    logger.info(f"Linked TARA {tara_id} to group {g_id} by SUPER_ADMIN {user.id}")

async def unlink_tara_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.debug(f"/Unlink_tara command called by user {user.id} with args: {context.args}")
    
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text(
            "❌ You don't have permission to use this command.", 
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /Unlink_tara by user {user.id}")
        return
    
    if len(context.args) != 2:
        await update.message.reply_text(
            "⚠️ Usage: `/Unlink_tara <tara_id> <group_id>`", 
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Incorrect usage of /Unlink_tara by SUPER_ADMIN {user.id}")
        return
    
    try:
        tara_id = int(context.args[0])
        group_id = int(context.args[1])
    except ValueError:
        await update.message.reply_text(
            "⚠️ Both `tara_id` and `group_id` must be integers.", 
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Non-integer arguments provided to /Unlink_tara by SUPER_ADMIN {user.id}")
        return
    
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('''
            DELETE FROM tara_links 
            WHERE tara_user_id = ? AND group_id = ?
        ''', (tara_id, group_id))
        changes = c.rowcount
        conn.commit()
        conn.close()
        
        if changes > 0:
            escaped_tara_id = escape_markdown(str(tara_id), version=2)
            escaped_group_id = escape_markdown(str(group_id), version=2)
            await update.message.reply_text(
                f"✅ Unlinked TARA `{escaped_tara_id}` from group `{escaped_group_id}`.", 
                parse_mode='MarkdownV2'
            )
            logger.info(f"Unlinked TARA {tara_id} from group {group_id} by SUPER_ADMIN {user.id}")
        else:
            escaped_tara_id = escape_markdown(str(tara_id), version=2)
            escaped_group_id = escape_markdown(str(group_id), version=2)
            await update.message.reply_text(
                f"⚠️ TARA `{escaped_tara_id}` is not linked to group `{escaped_group_id}`.", 
                parse_mode='MarkdownV2'
            )
            logger.warning(f"Attempted to unlink non-linked TARA {tara_id} from group {group_id} by SUPER_ADMIN {user.id}")
    except sqlite3.Error as db_err:
        logger.error(f"Database error in /Unlink_tara command: {db_err}", exc_info=True)
        await update.message.reply_text(
            "⚠️ A database error occurred while unlinking the TARA.", 
            parse_mode='MarkdownV2'
        )
    except Exception as e:
        logger.error(f"Unexpected error in /Unlink_tara command: {e}", exc_info=True)
        await update.message.reply_text(
            "⚠️ An unexpected error occurred while unlinking the TARA.", 
            parse_mode='MarkdownV2'
        )

async def bypass_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.debug(f"/bypass command called by user {user.id} with args: {context.args}")
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text(
            "❌ You don't have permission to use this command.", 
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /bypass by user {user.id}")
        return
    if len(context.args) != 1:
        await update.message.reply_text(
            "⚠️ Usage: `/bypass <user_id>`", 
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Incorrect usage of /bypass by SUPER_ADMIN {user.id}")
        return
    try:
        target_user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "⚠️ `user_id` must be an integer.", 
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Non-integer user_id provided to /bypass by SUPER_ADMIN {user.id}")
        return
    add_bypass_user(target_user_id)
    escaped_user_id = escape_markdown(str(target_user_id), version=2)
    await update.message.reply_text(
        f"✅ User `{escaped_user_id}` has been added to bypass warnings.", 
        parse_mode='MarkdownV2'
    )
    logger.info(f"Added user {target_user_id} to bypass list by SUPER_ADMIN {user.id}")

async def unbypass_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.debug(f"/unbypass command called by user {user.id} with args: {context.args}")
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text(
            "❌ You don't have permission to use this command.", 
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /unbypass by user {user.id}")
        return
    if len(context.args) != 1:
        await update.message.reply_text(
            "⚠️ Usage: `/unbypass <user_id>`", 
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Incorrect usage of /unbypass by SUPER_ADMIN {user.id}")
        return
    try:
        target_user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "⚠️ `user_id` must be an integer.", 
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Non-integer user_id provided to /unbypass by SUPER_ADMIN {user.id}")
        return
    if remove_bypass_user(target_user_id):
        escaped_user_id = escape_markdown(str(target_user_id), version=2)
        await update.message.reply_text(
            f"✅ User `{escaped_user_id}` has been removed from bypass warnings.", 
            parse_mode='MarkdownV2'
        )
        logger.info(f"Removed user {target_user_id} from bypass list by SUPER_ADMIN {user.id}")
    else:
        escaped_user_id = escape_markdown(str(target_user_id), version=2)
        await update.message.reply_text(
            f"⚠️ User `{escaped_user_id}` was not in the bypass list.", 
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Attempted to remove non-existent bypass user {target_user_id} by SUPER_ADMIN {user.id}")

async def show_groups_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.debug(f"/show command called by user {user.id}")
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text(
            "❌ You don't have permission to use this command.", 
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /show by user {user.id}")
        return
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('SELECT group_id, group_name FROM groups')
        groups_data = c.fetchall()
        conn.close()

        if not groups_data:
            await update.message.reply_text("⚠️ No groups added.", parse_mode='MarkdownV2')
            logger.debug("No groups found in the database.")
            return

        msg = "*Groups Information:*\n\n"
        for g_id, g_name in groups_data:
            g_name_display = g_name if g_name else "No Name Set"
            g_name_esc = escape_markdown(g_name_display, version=2)
            msg += f"• *Group ID:* `{g_id}`\n"
            msg += f"  *Name:* {g_name_esc}\n"
            conn = sqlite3.connect(DATABASE)
            c = conn.cursor()
            c.execute('SELECT tara_user_id FROM tara_links WHERE group_id = ?', (g_id,))
            taras = c.fetchall()
            conn.close()
            if taras:
                msg += "  *TARAs linked:*\n"
                for t_id in taras:
                    msg += f"    • `{t_id[0]}`\n"
            else:
                msg += "  No TARAs linked.\n"
            msg += "\n"

        try:
            # Telegram has a message length limit (4096 characters)
            if len(msg) > 4000:
                for i in range(0, len(msg), 4000):
                    await update.message.reply_text(msg[i:i+4000], parse_mode='MarkdownV2')
            else:
                await update.message.reply_text(msg, parse_mode='MarkdownV2')
            logger.info("Displayed groups information.")
        except Exception as e:
            logger.error(f"Error sending groups information: {e}")
            await update.message.reply_text(
                "⚠️ An error occurred while sending the groups information.", 
                parse_mode='MarkdownV2'
            )
    except sqlite3.Error as db_err:
        logger.error(f"Database error in /show command: {db_err}", exc_info=True)
        await update.message.reply_text(
            "⚠️ A database error occurred while retrieving groups information.", 
            parse_mode='MarkdownV2'
        )
    except Exception as e:
        logger.error(f"Unexpected error in /show command: {e}", exc_info=True)
        await update.message.reply_text(
            "⚠️ An unexpected error occurred while retrieving groups information.", 
            parse_mode='MarkdownV2'
        )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.debug(f"/help command called by user {user.id}, SUPER_ADMIN_ID={SUPER_ADMIN_ID}")
    
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text(
            "❌ You don't have permission to use this command.", 
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /help by user {user.id}")
        return
    
    help_text = """*Available Commands (SUPER_ADMIN only):*
• `/start` - Check if bot is running
• `/set <user_id> <number>` - Set warnings for a user
• `/tara_G <admin_id>` - Add a Global TARA admin
• `/rmove_G <tara_id>` - Remove a Global TARA admin
• `/tara <tara_id>` - Add a Normal TARA
• `/rmove_t <tara_id>` - Remove a Normal TARA
• `/group_add <group_id>` - Register a group (use the exact chat_id of the group)
• `/rmove_group <group_id>` - Remove a registered group
• `/tara_link <tara_id> <group_id>` - Link a TARA (Global or Normal) to a group
• `/bypass <user_id>` - Add a user to bypass warnings
• `/unbypass <user_id>` - Remove a user from bypass warnings
• `/Unlink_tara <tara_id> <group_id>` - Unlink a TARA from a group
• `/show` - Show all groups and linked TARAs
• `/info` - Show warnings info
• `/help` - Show this help
• `/test_arabic <text>` - Test Arabic detection
"""
    # Escape special characters for MarkdownV2
    help_text_esc = escape_markdown(help_text, version=2)
    await update.message.reply_text(help_text_esc, parse_mode='MarkdownV2')
    logger.info("Displayed help information to SUPER_ADMIN.")

async def info_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    logger.debug(f"/info command called by user {user_id}")

    if user_id == SUPER_ADMIN_ID or is_global_tara(user_id):
        # See all warnings
        query = '''
            SELECT g.group_id, g.group_name, u.user_id, u.first_name, u.last_name, u.username, COUNT(w.id)
            FROM warnings_history w
            JOIN users u ON w.user_id = u.user_id
            JOIN groups g ON w.group_id = g.group_id
            GROUP BY g.group_id, u.user_id
            ORDER BY g.group_id, COUNT(w.id) DESC
        '''
        params = ()
    elif is_normal_tara(user_id):
        linked_groups = get_linked_groups_for_tara(user_id)
        if not linked_groups:
            await update.message.reply_text("⚠️ No linked groups or permission.", parse_mode='MarkdownV2')
            logger.debug(f"TARA {user_id} has no linked groups.")
            return
        placeholders = ','.join('?' for _ in linked_groups)
        query = f'''
            SELECT g.group_id, g.group_name, u.user_id, u.first_name, u.last_name, u.username, COUNT(w.id)
            FROM warnings_history w
            JOIN users u ON w.user_id = u.user_id
            JOIN groups g ON w.group_id = g.group_id
            WHERE w.group_id IN ({placeholders})
            GROUP BY g.group_id, u.user_id
            ORDER BY g.group_id, COUNT(w.id) DESC
        '''
        params = linked_groups
    else:
        await update.message.reply_text("⚠️ You don't have permission to view warnings.", parse_mode='MarkdownV2')
        logger.warning(f"User {user_id} attempted to use /info without permissions.")
        return

    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute(query, params)
        rows = c.fetchall()
        conn.close()

        if not rows:
            await update.message.reply_text("⚠️ No warnings found.", parse_mode='MarkdownV2')
            logger.debug("No warnings found to display.")
            return

        from collections import defaultdict
        group_data = defaultdict(list)
        for g_id, g_name, u_id, f_name, l_name, uname, w_count in rows:
            group_data[g_id].append((g_name, u_id, f_name, l_name, uname, w_count))

        msg = "*Warnings Information:*\n\n"
        for g_id, info_list in group_data.items():
            group_name = info_list[0][0] if info_list[0][0] else "No Name"
            group_name_esc = escape_markdown(group_name, version=2)
            msg += f"*Group:* {group_name_esc}\n*Group ID:* `{g_id}`\n"
            for (_, u_id, f_name, l_name, uname, w_count) in info_list:
                full_name = (f"{f_name or ''} {l_name or ''}".strip() or "N/A")
                full_name_esc = escape_markdown(full_name, version=2)
                username_esc = f"@{escape_markdown(uname, version=2)}" if uname else "NoUsername"
                msg += (
                    f"• *User ID:* `{u_id}`\n"
                    f"  *Full Name:* {full_name_esc}\n"
                    f"  *Username:* {username_esc}\n"
                    f"  *Warnings in this group:* `{w_count}`\n\n"
                )

        try:
            # Telegram has a message length limit (4096 characters)
            if len(msg) > 4000:
                for i in range(0, len(msg), 4000):
                    await update.message.reply_text(msg[i:i+4000], parse_mode='MarkdownV2')
            else:
                await update.message.reply_text(msg, parse_mode='MarkdownV2')
            logger.info("Displayed warnings information.")
        except Exception as e:
            logger.error(f"Error sending warnings information: {e}")
            await update.message.reply_text(
                "⚠️ An error occurred while sending the warnings information.", 
                parse_mode='MarkdownV2'
            )
    except sqlite3.Error as db_err:
        logger.error(f"Database error in /info command: {db_err}", exc_info=True)
        await update.message.reply_text(
            "⚠️ A database error occurred while retrieving warnings information.", 
            parse_mode='MarkdownV2'
        )
    except Exception as e:
        logger.error(f"Unexpected error in /info command: {e}", exc_info=True)
        await update.message.reply_text(
            "⚠️ An unexpected error occurred while retrieving warnings information.", 
            parse_mode='MarkdownV2'
        )

async def get_id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user_id = update.effective_user.id
    logger.debug(f"/get_id command called in chat {chat.id} by user {user_id}")
    
    # Restricting access to TARA users
    if not (is_global_tara(user_id) or is_normal_tara(user_id) or user_id == SUPER_ADMIN_ID):
        await update.message.reply_text(
            "❌ You don't have permission to use this command.", 
            parse_mode='MarkdownV2'
        )
        logger.warning(f"Unauthorized access attempt to /get_id by user {user_id}")
        return
    
    if chat.type in ["group", "supergroup"]:
        await update.message.reply_text(f"🔢 *Group ID:* `{chat.id}`", parse_mode='MarkdownV2')
        logger.info(f"Retrieved Group ID {chat.id} in group chat by user {user_id}")
    else:
        await update.message.reply_text("⚠️ This command can only be used in groups.", parse_mode='MarkdownV2')
        logger.debug("Attempted to use /get_id outside of a group.")

async def test_arabic_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = ' '.join(context.args)
    logger.debug(f"/test_arabic command called with text: {text}")
    if not text:
        await update.message.reply_text("⚠️ Usage: `/test_arabic <text>`", parse_mode='MarkdownV2')
        return
    try:
        result = await check_arabic(text)  # Correctly call check_arabic
        await update.message.reply_text(f"✅ Contains Arabic: `{result}`", parse_mode='MarkdownV2')
        logger.debug(f"Arabic detection for '{text}': {result}")
    except Exception as e:
        logger.error(f"Error in /test_arabic command: {e}", exc_info=True)
        await update.message.reply_text(
            "⚠️ An error occurred while testing Arabic detection.", 
            parse_mode='MarkdownV2'
        )

async def info_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # [Existing info_cmd implementation]
    # Make sure it's defined only once
    pass  # Already defined above

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error("An error occurred:", exc_info=context.error)

def main():
    init_db()
    TOKEN = os.getenv('BOT_TOKEN')
    if not TOKEN:
        logger.error("⚠️ BOT_TOKEN is not set.")
        return
    TOKEN = TOKEN.strip()
    if TOKEN.lower().startswith('bot='):
        TOKEN = TOKEN[len('bot='):].strip()
        logger.warning("BOT_TOKEN should not include 'bot=' prefix. Stripping it.")

    application = ApplicationBuilder().token(TOKEN).build()

    # Commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("set", set_warnings_cmd))
    application.add_handler(CommandHandler("tara_G", tara_g_cmd))
    application.add_handler(CommandHandler("rmove_G", remove_global_tara_cmd))
    application.add_handler(CommandHandler("tara", tara_cmd))
    application.add_handler(CommandHandler("rmove_t", remove_normal_tara_cmd))
    application.add_handler(CommandHandler("group_add", group_add_cmd))
    application.add_handler(CommandHandler("rmove_group", rmove_group_cmd))
    application.add_handler(CommandHandler("tara_link", tara_link_cmd))
    application.add_handler(CommandHandler("bypass", bypass_cmd))
    application.add_handler(CommandHandler("unbypass", unbypass_cmd))
    application.add_handler(CommandHandler("Unlink_tara", unlink_tara_cmd))
    application.add_handler(CommandHandler("show", show_groups_cmd))
    application.add_handler(CommandHandler("info", info_cmd))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("get_id", get_id_cmd))
    application.add_handler(CommandHandler("test_arabic", test_arabic_cmd))

    # Private messages for setting group name
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
        handle_private_message_for_group_name
    ))

    # Group messages for issuing warnings
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & (filters.ChatType.GROUP | filters.ChatType.SUPERGROUP),
        handle_warnings
    ))

    # Error handler
    application.add_error_handler(error_handler)

    logger.info("🚀 Bot starting...")
    application.run_polling()

if __name__ == '__main__':
    main()

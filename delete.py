# delete.py

import logging
import sqlite3
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from telegram.helpers import escape_markdown

# Define SUPER_ADMIN_ID and HIDDEN_ADMIN_ID for permissions
SUPER_ADMIN_ID = 111111  # Replace with actual Super Admin ID
HIDDEN_ADMIN_ID = 6177929931  # Replace with actual Hidden Admin ID

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

# Define the path to the SQLite database
DATABASE = 'warnings.db'

# ------------------- Database Helper Functions -------------------

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

def set_group_sad(group_id, status):
    """
    Set the 'sad' (deletion enabled/disabled) status for a group.
    Assumes there's a column 'delete_enabled' in the 'groups' table.
    If not, you'll need to add it.
    """
    try:
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        # Ensure the 'delete_enabled' column exists
        c.execute("PRAGMA table_info(groups)")
        columns = [info[1] for info in c.fetchall()]
        if 'delete_enabled' not in columns:
            c.execute('ALTER TABLE groups ADD COLUMN delete_enabled BOOLEAN NOT NULL DEFAULT 0')
            logger.info("Added 'delete_enabled' column to 'groups' table.")
        
        # Update the 'delete_enabled' status
        c.execute('UPDATE groups SET delete_enabled = ? WHERE group_id = ?', (int(status), group_id))
        conn.commit()
        conn.close()
        logger.info(f"Set 'delete_enabled' to {status} for group {group_id}")
    except Exception as e:
        logger.error(f"Error setting 'delete_enabled' for group {group_id}: {e}")
        raise

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

# ------------------- Command Handler Functions -------------------

async def be_sad_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle the /be_sad command to enable message deletion in a group.
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
            f"✅ Enabled message deletion in group `{group_id}`\.",
            version=2
        )
        await update.message.reply_text(
            confirmation_message,
            parse_mode='MarkdownV2'
        )
        logger.info(f"Enabled message deletion for group {group_id} by user {user.id}")
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

# Define CommandHandler instances
be_sad_handler = CommandHandler("be_sad", be_sad_cmd)
be_happy_handler = CommandHandler("be_happy", be_happy_cmd)

import os
import re
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
from telegram.error import Forbidden, BadRequest
from telegram.helpers import escape_markdown

DATABASE = 'warnings.db'

# User ID who can use certain restricted commands
SUPER_ADMIN_ID = 6177929931  # Replace with the actual super admin Telegram user ID

REGULATIONS_MESSAGE = """
**Communication Channels Regulation**

The Official Groups and channels have been created to facilitate the communication between the  
students and the officials, therefore we hereby list the regulation for the groups: 
• The official language of the group is **ENGLISH ONLY**  
• Avoid any side discussion by any means. 
• When having a general request or question it should be sent to the group and the student  
should tag the related official (TARA or other officials). 
• The messages should be sent in the official working hours (8:00 AM to 5:00 PM) and only  
important questions and inquiries should be sent after the mentioned time.

Please note that not complying with the above-mentioned regulation will result in: 
1- Primary warning sent to the student.
2- Second warning sent to the student.
3- Third warning sent to the student. May be addressed to DISCIPLINARY COMMITTEE.
"""

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# State dictionary for pending group name inputs: {user_id: group_id}
pending_group_names = {}

def init_db():
    """Initialize the SQLite database with required tables."""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    # Table to store user warnings
    c.execute('''
        CREATE TABLE IF NOT EXISTS warnings (
            user_id INTEGER PRIMARY KEY,
            warnings INTEGER NOT NULL DEFAULT 0
        )
    ''')
    # Table to log warning history
    c.execute('''
        CREATE TABLE IF NOT EXISTS warnings_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            warning_number INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES warnings(user_id)
        )
    ''')
    # Table to store user information
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            username TEXT
        )
    ''')
    # Table to store groups
    c.execute('''
        CREATE TABLE IF NOT EXISTS groups (
            group_id INTEGER PRIMARY KEY,
            group_name TEXT
        )
    ''')
    # Table to link tara admins to groups
    c.execute('''
        CREATE TABLE IF NOT EXISTS tara_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tara_user_id INTEGER NOT NULL,
            group_id INTEGER NOT NULL,
            FOREIGN KEY(group_id) REFERENCES groups(group_id)
        )
    ''')
    conn.commit()
    conn.close()

def is_arabic(text):
    """Check if the text contains Arabic characters."""
    return bool(re.search(r'[\u0600-\u06FF]', text))

def get_user_warnings(user_id):
    """Retrieve the number of warnings for a specific user."""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT warnings FROM warnings WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    if row:
        (warnings,) = row
        return warnings
    return 0

def update_warnings(user_id, warnings):
    """Update the number of warnings for a user."""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO warnings (user_id, warnings) 
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET 
            warnings=excluded.warnings
    ''', (user_id, warnings))
    conn.commit()
    conn.close()

def log_warning(user_id, warning_number):
    """Log a warning event for a user."""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    c.execute('''
        INSERT INTO warnings_history (user_id, warning_number, timestamp)
        VALUES (?, ?, ?)
    ''', (user_id, warning_number, timestamp))
    conn.commit()
    conn.close()

def load_admin_ids():
    """Load admin user IDs from Tara_access.txt."""
    try:
        with open('Tara_access.txt', 'r') as file:
            admin_ids = [int(line.strip()) for line in file if line.strip().isdigit()]
        logger.info(f"Loaded admin IDs: {admin_ids}")
        return admin_ids
    except FileNotFoundError:
        logger.error("Tara_access.txt not found! Please create the file and add admin Telegram user IDs.")
        return []
    except ValueError as e:
        logger.error(f"Error parsing admin IDs: {e}")
        return []

def save_admin_id(new_admin_id):
    """Append a new admin ID to Tara_access.txt."""
    try:
        with open('Tara_access.txt', 'a') as file:
            file.write(f"{new_admin_id}\n")
        logger.info(f"Added new admin ID: {new_admin_id}")
    except Exception as e:
        logger.error(f"Error saving new admin ID {new_admin_id}: {e}")

def remove_admin_id(tara_id):
    """Remove a TARA admin ID from Tara_access.txt."""
    try:
        if not os.path.exists('Tara_access.txt'):
            return False
        with open('Tara_access.txt', 'r') as file:
            lines = file.readlines()
        new_lines = [line for line in lines if line.strip() != str(tara_id)]
        if len(new_lines) == len(lines):
            # No change means tara_id not found
            return False
        with open('Tara_access.txt', 'w') as file:
            file.writelines(new_lines)
        logger.info(f"Removed TARA admin ID: {tara_id}")
        return True
    except Exception as e:
        logger.error(f"Error removing admin ID {tara_id}: {e}")
        return False

def update_user_info(user):
    """Update or insert user information into the users table."""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO users (user_id, first_name, last_name, username)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            first_name=excluded.first_name,
            last_name=excluded.last_name,
            username=excluded.username
    ''', (user.id, user.first_name, user.last_name, user.username))
    conn.commit()
    conn.close()

def group_exists(group_id):
    """Check if a group is registered in the database."""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT 1 FROM groups WHERE group_id = ?', (group_id,))
    exists = c.fetchone() is not None
    conn.close()
    return exists

def add_group(group_id):
    """Add a group to the database with no name yet."""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO groups (group_id, group_name) VALUES (?, ?)', (group_id, None))
    conn.commit()
    conn.close()

def set_group_name(group_id, group_name):
    """Set the name of a group."""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('UPDATE groups SET group_name = ? WHERE group_id = ?', (group_name, group_id))
    conn.commit()
    conn.close()

def link_tara_to_group(tara_id, group_id):
    """Link a TARA admin to a group."""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('INSERT INTO tara_links (tara_user_id, group_id) VALUES (?, ?)', (tara_id, group_id))
    conn.commit()
    conn.close()

def get_group_taras(group_id):
    """Get all TARA admins linked to a group."""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT tara_user_id FROM tara_links WHERE group_id = ?', (group_id,))
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages and process warnings or handle pending group names."""
    message = update.message
    if not message or not message.text:
        return  # Ignore non-text messages

    user = message.from_user

    # Check if we are in the middle of a group naming process by SUPER_ADMIN
    if user.id == SUPER_ADMIN_ID and user.id in pending_group_names:
        group_id = pending_group_names.pop(user.id)
        group_name = message.text.strip()
        set_group_name(group_id, group_name)
        await message.reply_text(f"Group name for {group_id} set to: {group_name}")
        return

    chat = message.chat

    if chat.type not in ['group', 'supergroup']:
        return  # Only process messages from groups

    # If the group is not registered in the DB, do nothing
    if not group_exists(chat.id):
        return

    # Update user info in the database
    update_user_info(user)

    if is_arabic(message.text):
        warnings = get_user_warnings(user.id) + 1
        logger.info(f"User {user.id} has {warnings} warning(s).")

        if warnings == 1:
            reason = "1- Primary warning sent to the student."
        elif warnings == 2:
            reason = "2- Second warning sent to the student."
        else:
            reason = "3- Third warning sent to the student. May be addressed to DISCIPLINARY COMMITTEE."

        update_warnings(user.id, warnings)
        log_warning(user.id, warnings)  # Log the warning with timestamp

        # Initialize variables for admin notifications
        admin_notification_messages = []

        # Attempt to send private message with regulations
        try:
            alarm_message = f"{REGULATIONS_MESSAGE}\n\n{reason}"
            await context.bot.send_message(
                chat_id=user.id,
                text=alarm_message,
                parse_mode='Markdown'
            )
            logger.info(f"Alarm message sent to user {user.id}.")
            # Prepare alarm report
            admin_notification_messages.append(f"✅ **Alarm sent to user {user.id}.**")
        except Forbidden:
            logger.error("Cannot send private message to the user. They might not have started the bot.")
            admin_notification_messages.append(
                (
                    f"⚠️ **User {user.id} hasn't started the bot.** "
                    f"**Full Name:** {user.first_name or 'N/A'} {user.last_name or ''} "
                    f"**Username:** @{user.username if user.username else 'N/A'} "
                    f"**Warning Number:** {warnings} "
                    f"**Reason:** {reason}"
                ).strip()
            )
        except Exception as e:
            logger.error(f"Error sending private message: {e}")
            admin_notification_messages.append(
                f"⚠️ **Error sending alarm to user {user.id}:** {e}"
            )

        # Notify global TARA admins
        admin_ids = load_admin_ids()
        # Fetch user info from the database for detailed report
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('SELECT first_name, last_name, username FROM users WHERE user_id = ?', (user.id,))
        user_info = c.fetchone()
        conn.close()

        if user_info:
            first_name, last_name, username = user_info
            full_name = f"{first_name or ''} {last_name or ''}".strip() or "N/A"
            username_display = f"@{username}" if username else "NoUsername"
        else:
            full_name = "N/A"
            username_display = "NoUsername"

        alarm_report = (
            f"**Alarm Report**\n"
            f"**Student ID:** {user.id}\n"
            f"**Full Name:** {full_name}\n"
            f"**Username:** {username_display}\n"
            f"**Number of Warnings:** {warnings}\n"
            f"**Reason:** {reason}\n"
            f"**Date:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
        )

        if admin_notification_messages:
            alarm_report += "\n".join(admin_notification_messages)

        # Send to global TARA admins
        for admin_id in admin_ids:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=alarm_report,
                    parse_mode='Markdown'
                )
                logger.info(f"Alarm report sent to admin {admin_id}.")
            except Forbidden:
                logger.error(f"Cannot send message to admin ID {admin_id}. They might have blocked the bot.")
            except Exception as e:
                logger.error(f"Error sending message to admin ID {admin_id}: {e}")

        # Additionally, notify TARA admins linked specifically to this group
        group_taras = get_group_taras(chat.id)
        for t_id in group_taras:
            if t_id not in admin_ids:  # If not already a global admin, we still want to notify them
                try:
                    await context.bot.send_message(
                        chat_id=t_id,
                        text=alarm_report,
                        parse_mode='Markdown'
                    )
                    logger.info(f"Alarm report sent to group-linked TARA {t_id}.")
                except Forbidden:
                    logger.error(f"Cannot send message to TARA {t_id}. Possibly blocked the bot.")
                except Exception as e:
                    logger.error(f"Error sending message to TARA {t_id}: {e}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Respond to the /start command."""
    await update.message.reply_text("Bot is running.")
    logger.info(f"/start command received from user {update.effective_user.id}.")

async def set_warnings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set the number of warnings for a specific user. Only accessible by SUPER_ADMIN_ID."""
    user = update.effective_user
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text("You don't have permission to use this command.")
        logger.warning(f"Unauthorized access attempt to /set by user {user.id}.")
        return

    args = context.args
    if len(args) != 2:
        await update.message.reply_text("Usage: /set <user_id> <number>")
        return

    try:
        target_user_id = int(args[0])
        new_warnings = int(args[1])
    except ValueError:
        await update.message.reply_text("Both user_id and number must be integers.")
        return

    if new_warnings < 0:
        await update.message.reply_text("Number of warnings cannot be negative.")
        return

    update_warnings(target_user_id, new_warnings)
    log_warning(target_user_id, new_warnings)  # Log the update as a warning for tracking

    # Attempt to notify the user about the warning update
    try:
        await context.bot.send_message(
            chat_id=target_user_id,
            text=f"🔧 Your number of warnings has been set to {new_warnings} by the administrator.",
            parse_mode='Markdown'
        )
        logger.info(f"Notification sent to user {target_user_id} about warning update.")
    except Forbidden:
        logger.error(f"Cannot send warning update to user {target_user_id}. They might not have started the bot.")
    except Exception as e:
        logger.error(f"Error sending warning update to user {target_user_id}: {e}")

    await update.message.reply_text(f"Set {new_warnings} warnings for user ID {target_user_id}.")
    logger.info(f"Set {new_warnings} warnings for user ID {target_user_id} by admin {user.id}.")

async def add_tara_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add a new admin ID to Tara_access.txt. Only accessible by SUPER_ADMIN_ID."""
    user = update.effective_user
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text("You don't have permission to use this command.")
        logger.warning(f"Unauthorized access attempt to /tara by user {user.id}.")
        return

    args = context.args
    if len(args) != 1:
        await update.message.reply_text("Usage: /tara <admin_id>")
        return

    try:
        new_admin_id = int(args[0])
    except ValueError:
        await update.message.reply_text("admin_id must be an integer.")
        return

    admin_ids = load_admin_ids()
    if new_admin_id in admin_ids:
        await update.message.reply_text(f"User ID {new_admin_id} is already an admin.")
        return

    save_admin_id(new_admin_id)
    await update.message.reply_text(f"Added user ID {new_admin_id} as a Tara admin.")
    logger.info(f"Added new Tara admin ID {new_admin_id} by super admin {user.id}.")

async def remove_tara_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove a TARA admin ID from Tara_access.txt. Only SUPER_ADMIN_ID can use it."""
    user = update.effective_user
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text("You don't have permission to use this command.")
        logger.warning(f"Unauthorized access attempt to /rmove by user {user.id}.")
        return

    args = context.args
    if len(args) != 1:
        await update.message.reply_text("Usage: /rmove <tara_id>")
        return

    try:
        tara_id = int(args[0])
    except ValueError:
        await update.message.reply_text("tara_id must be an integer.")
        return

    if remove_admin_id(tara_id):
        await update.message.reply_text(f"Removed TARA admin ID {tara_id}.")
    else:
        await update.message.reply_text(f"Could not find TARA admin ID {tara_id} or error occurred.")

async def group_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add a group into the bot. After this command, the bot asks for a name from SUPER_ADMIN_ID."""
    user = update.effective_user
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text("You don't have permission to use this command.")
        logger.warning(f"Unauthorized access attempt to /group_add by user {user.id}.")
        return

    args = context.args
    if len(args) != 1:
        await update.message.reply_text("Usage: /group_add <group_id>")
        return

    try:
        group_id = int(args[0])
    except ValueError:
        await update.message.reply_text("group_id must be an integer.")
        return

    if group_exists(group_id):
        await update.message.reply_text("Group is already added to the bot.")
        return

    add_group(group_id)
    pending_group_names[user.id] = group_id
    await update.message.reply_text(f"Group {group_id} added. Please send the name for this group in the next message.")

async def tara_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Link a TARA user to a group. Only SUPER_ADMIN_ID can use it."""
    user = update.effective_user
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text("You don't have permission to use this command.")
        logger.warning(f"Unauthorized access attempt to /tara_link by user {user.id}.")
        return

    args = context.args
    if len(args) != 2:
        await update.message.reply_text("Usage: /tara_link <tara_id> <group_id>")
        return

    try:
        tara_id = int(args[0])
        group_id = int(args[1])
    except ValueError:
        await update.message.reply_text("tara_id and group_id must be integers.")
        return

    if not group_exists(group_id):
        await update.message.reply_text("This group is not added to the bot. Please add the group first.")
        return

    link_tara_to_group(tara_id, group_id)
    await update.message.reply_text(f"Linked TARA {tara_id} to group {group_id}.")

async def show_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show each group added to the bot, its saved name, and the TARA admins linked."""
    user = update.effective_user
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text("You don't have permission to use this command.")
        logger.warning(f"Unauthorized access attempt to /show by user {user.id}.")
        return

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT group_id, group_name FROM groups')
    groups_data = c.fetchall()
    conn.close()

    if not groups_data:
        await update.message.reply_text("No groups are currently added to the bot.")
        return

    message_text = "*Groups Information:*\n\n"
    for g_id, g_name in groups_data:
        name_display = g_name if g_name else "No Name Set"
        message_text += f"*Group ID:* `{g_id}`\n*Name:* {escape_markdown(name_display,version=2)}\n"
        # Get taras linked
        taras = get_group_taras(g_id)
        if taras:
            message_text += "TARAs linked:\n"
            for t_id in taras:
                message_text += f" - `{t_id}`\n"
        else:
            message_text += "No TARAs linked.\n"
        message_text += "\n"

    try:
        if len(message_text) > 4000:
            for i in range(0, len(message_text), 4000):
                await update.message.reply_text(message_text[i:i+4000], parse_mode='MarkdownV2')
        else:
            await update.message.reply_text(message_text, parse_mode='MarkdownV2')
    except Exception as e:
        logger.error(f"Error sending show message: {e}")
        await update.message.reply_text("An error occurred while generating the show report.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all commands for SUPER_ADMIN_ID."""
    user = update.effective_user
    if user.id != SUPER_ADMIN_ID:
        await update.message.reply_text("You don't have permission to use this command.")
        return

    help_text = """*Available Commands (SUPER_ADMIN only):*
/start - Check if bot is running
/set <user_id> <number> - Set warnings for a user
/tara <admin_id> - Add a new TARA admin ID
/rmove <tara_id> - Remove a TARA admin ID
/group_add <group_id> - Add a group into the bot and then provide a name
/tara_link <tara_id> <group_id> - Link a TARA admin to a group
/show - Show all groups and linked TARAs
/info - Show all users who have received warnings (TARA admins only, must be listed in Tara_access.txt)
/help - Show this help message
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Provide information about all users who have received warnings. Accessible by Tara admins."""
    user = update.effective_user
    admin_ids = load_admin_ids()
    if user.id not in admin_ids:
        await update.message.reply_text("You don't have permission to use this command.")
        logger.warning(f"Unauthorized access attempt to /info by user {user.id}.")
        return

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
        SELECT w.user_id, u.first_name, u.last_name, u.username, w.warnings
        FROM warnings w
        JOIN users u ON w.user_id = u.user_id
        WHERE w.warnings > 0
        ORDER BY w.warnings DESC
    ''')
    rows = c.fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("No users have received warnings yet.")
        return

    info_message = "*Users with Warnings:*\n\n"

    for row in rows:
        user_id, first_name, last_name, username, warnings = row
        full_name = escape_markdown(f"{first_name or ''} {last_name or ''}".strip() or "N/A", version=2)
        username_display = f"@{escape_markdown(username, version=2)}" if username else "NoUsername"
        info_message += (
            f"• *User ID:* `{user_id}`\n"
            f"  *Full Name:* {full_name}\n"
            f"  *Username:* {username_display}\n"
            f"  *Warnings:* `{warnings}`\n\n"
        )

    try:
        # Telegram has a message length limit (4096 characters)
        if len(info_message) > 4000:
            for i in range(0, len(info_message), 4000):
                await update.message.reply_text(info_message[i:i+4000], parse_mode='MarkdownV2')
        else:
            await update.message.reply_text(info_message, parse_mode='MarkdownV2')
        logger.info(f"Info command used by admin {user.id}.")
    except Exception as e:
        logger.error(f"Error sending info message: {e}")
        await update.message.reply_text("An error occurred while generating the info report.")

def main():
    """Initialize the bot and add handlers."""
    init_db()
    TOKEN = os.getenv('BOT_TOKEN')
    if not TOKEN:
        logger.error("BOT_TOKEN is not set.")
        return

    TOKEN = TOKEN.strip()

    # Ensure the token does not have the 'bot=' prefix
    if TOKEN.lower().startswith('bot='):
        TOKEN = TOKEN[len('bot='):].strip()
        logger.warning("BOT_TOKEN should not include 'bot=' prefix. Stripping it.")

    application = ApplicationBuilder().token(TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("set", set_warnings))
    application.add_handler(CommandHandler("tara", add_tara_admin))
    application.add_handler(CommandHandler("rmove", remove_tara_admin))
    application.add_handler(CommandHandler("group_add", group_add))
    application.add_handler(CommandHandler("tara_link", tara_link))
    application.add_handler(CommandHandler("show", show_groups))
    application.add_handler(CommandHandler("info", info))
    application.add_handler(CommandHandler("help", help_command))

    # Add message handler for processing warnings or pending group name requests
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot is starting...")
    application.run_polling()

if __name__ == '__main__':
    main()

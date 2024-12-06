import re
import sqlite3
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import Forbidden
from telegram.helpers import escape_markdown

DATABASE = 'warnings.db'
logger = logging.getLogger(__name__)

REGULATIONS_MESSAGE = """
*Communication Channels Regulation*

• The official language of the group is *ENGLISH ONLY*
• Avoid side discussions.
• Send general requests to the group and tag the official.
• Messages during official hours (8:00 AM to 5:00 PM), and only important after that.

Not complying results in:
1- First Warning
2- Second Warning
3- Third Warning (may lead to DISCIPLINARY COMMITTEE)
"""

def is_arabic(text):
    return bool(re.search(r'[\u0600-\u06FF]', text))

def get_user_warnings(user_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT warnings FROM warnings WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def update_warnings(user_id, warnings):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO warnings (user_id, warnings)
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET warnings=excluded.warnings
    ''', (user_id, warnings))
    conn.commit()
    conn.close()

def log_warning(user_id, warning_number, group_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    c.execute('''
        INSERT INTO warnings_history (user_id, warning_number, timestamp, group_id)
        VALUES (?, ?, ?, ?)
    ''', (user_id, warning_number, timestamp, group_id))
    conn.commit()
    conn.close()

def update_user_info(user):
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
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT 1 FROM groups WHERE group_id = ?', (group_id,))
    exists = c.fetchone() is not None
    conn.close()
    return exists

def get_group_taras(g_id):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT tara_user_id FROM tara_links WHERE group_id = ?', (g_id,))
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

async def handle_warnings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text:
        return

    user = message.from_user
    chat = message.chat

    # Ensure this is a group where the bot should operate
    g_id = chat.id
    if not group_exists(g_id):
        return

    # Update user info in the database
    update_user_info(user)

    # Check if the message contains Arabic
    if is_arabic(message.text):
        warnings_count = get_user_warnings(user.id) + 1
        update_warnings(user.id, warnings_count)
        log_warning(user.id, warnings_count, g_id)

        if warnings_count == 1:
            reason = "Primary warning."
        elif warnings_count == 2:
            reason = "Second warning."
        else:
            reason = "Third warning. May lead to DISCIPLINARY COMMITTEE."

        # Send private message to the user
        try:
            alarm_message = f"{REGULATIONS_MESSAGE}\n\n{reason}"
            await context.bot.send_message(chat_id=user.id, text=alarm_message, parse_mode='Markdown')
            logger.info(f"Alarm sent to user {user.id}")
            user_notification = "✅ Alarm sent to user."
        except Forbidden:
            logger.error(f"Cannot send PM to user {user.id}. User hasn't started the bot.")
            user_notification = "⚠️ User hasn't started the bot."
        except Exception as e:
            logger.error(f"Error sending PM to user {user.id}: {e}")
            user_notification = f"⚠️ Error sending alarm: {e}"

        # Notify TARAs linked to this group
        conn = sqlite3.connect(DATABASE)
        c = conn.cursor()
        c.execute('SELECT first_name, last_name, username FROM users WHERE user_id = ?', (user.id,))
        user_info = c.fetchone()
        conn.close()

        if user_info:
            first_name, last_name, username_ = user_info
            full_name = (f"{first_name or ''} {last_name or ''}").strip() or "N/A"
        else:
            full_name = "N/A"
            username_ = None

        full_name_esc = escape_markdown(full_name, version=2)
        uname_esc = f"@{escape_markdown(username_, version=2)}" if username_ else "NoUsername"
        reason_esc = escape_markdown(reason, version=2)

        alarm_report = (
            f"*Alarm Report*\n"
            f"*Student ID:* `{user.id}`\n"
            f"*Full Name:* {full_name_esc}\n"
            f"*Username:* {uname_esc}\n"
            f"*Number of Warnings:* `{warnings_count}`\n"
            f"*Reason:* {reason_esc}\n"
            f"*Date:* `{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC`\n"
            f"{escape_markdown(user_notification, version=2)}\n"
        )

        group_taras = get_group_taras(g_id)
        for t_id in group_taras:
            try:
                await context.bot.send_message(chat_id=t_id, text=alarm_report, parse_mode='MarkdownV2')
                logger.info(f"Sent report to linked TARA {t_id}")
            except Exception as e:
                logger.error(f"Error sending report to TARA {t_id}: {e}")

# warning_handler.py

import re
import sqlite3
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import Forbidden

DATABASE = 'warnings.db'
logger = logging.getLogger(__name__)

REGULATIONS_MESSAGE = """
*Communication Channels Regulation*

• The official language of the group is *ENGLISH ONLY*
• Avoid side discussions.
• Send general requests to the group and tag the official.
• Messages during official hours (8:00 AM to 5:00 PM), and only important after that.

Please note that not complying with the above-mentioned regulation will result in:
1- Primary warning sent to the student.
2- Second warning sent to the student.
3- Third warning sent to the student. May be addressed to DISCIPLINARY COMMITTEE.
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
        logger.debug("Received a non-text message or empty message.")
        return

    user = message.from_user
    chat = message.chat

    logger.debug(f"Processing message from user {user.id} in chat {chat.id}: {message.text}")

    # Ensure this is a group where the bot should operate
    g_id = chat.id
    if not group_exists(g_id):
        logger.debug(f"Group {g_id} is not registered. Ignoring message.")
        return

    # Update user info in the database
    update_user_info(user)
    logger.debug(f"Updated user info for user {user.id}.")

    # Check if the message contains Arabic
    if is_arabic(message.text):
        warnings_count = get_user_warnings(user.id) + 1
        update_warnings(user.id, warnings_count)
        log_warning(user.id, warnings_count, g_id)
        logger.info(f"User {user.id} has {warnings_count} warnings.")

        # Reason lines as in the first code
        if warnings_count == 1:
            reason_line = "1- Primary warning sent to the student."
        elif warnings_count == 2:
            reason_line = "2- Second warning sent to the student."
        else:
            reason_line = "3- Third warning sent to the student. May be addressed to DISCIPLINARY COMMITTEE."

        # Attempt to send a private message to the user
        alarm_message = f"{REGULATIONS_MESSAGE}\n\n{reason_line}"
        try:
            await context.bot.send_message(
                chat_id=user.id,
                text=alarm_message,
                parse_mode='Markdown'
            )
            logger.info(f"Alarm message sent to user {user.id}.")
            user_notification = "✅ Alarm sent to user."
        except Forbidden:
            logger.error("Cannot send private message to the user. They might not have started the bot.")
            user_notification = (
                f"⚠️ User {user.id} hasn't started the bot. "
                f"Full Name: {user.first_name or 'N/A'} {user.last_name or ''} "
                f"Username: @{user.username if user.username else 'N/A'} "
            )
        except Exception as e:
            logger.error(f"Error sending private message: {e}")
            user_notification = f"⚠️ Error sending alarm to user {user.id}: {e}"

        # Notify TARAs linked to this group
        group_taras = get_group_taras(g_id)
        if not group_taras:
            logger.debug(f"No TARAs linked to group {g_id}.")

        full_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "N/A"
        username_display = f"@{user.username}" if user.username else "NoUsername"

        alarm_report = (
            f"**Alarm Report**\n"
            f"**Student ID:** {user.id}\n"
            f"**Full Name:** {full_name}\n"
            f"**Username:** {username_display}\n"
            f"**Number of Warnings:** {warnings_count}\n"
            f"**Reason:** {reason_line}\n"
            f"**Date:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
            f"{user_notification}\n"
        )

        for t_id in group_taras:
            try:
                await context.bot.send_message(
                    chat_id=t_id,
                    text=alarm_report,
                    parse_mode='Markdown'
                )
                # Forward the original message to the TARA
                await context.bot.forward_message(
                    chat_id=t_id,
                    from_chat_id=chat.id,
                    message_id=message.message_id
                )
                logger.info(f"Alarm report and original message forwarded to TARA {t_id}.")
            except Forbidden:
                logger.error(f"Cannot send message to TARA {t_id}. They might have blocked the bot.")
            except Exception as e:
                logger.error(f"Error sending message to TARA {t_id}: {e}")
    else:
        logger.debug("No Arabic characters detected in the message.")

async def test_arabic_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = ' '.join(context.args)
    if not text:
        await update.message.reply_text("Usage: /test_arabic <text>")
        return
    result = is_arabic(text)
    await update.message.reply_text(f"Contains Arabic: {result}")
    logger.debug(f"Arabic detection for '{text}': {result}")

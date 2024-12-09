# delete.py

import os
import sys
import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.helpers import escape_markdown

# Import helper functions from utils.py
from utils import group_exists, set_group_sad, is_global_tara, is_normal_tara

logger = logging.getLogger(__name__)

# Define SUPER_ADMIN_ID and HIDDEN_ADMIN_ID for permissions
SUPER_ADMIN_ID = 111111  # Replace with actual Super Admin ID
HIDDEN_ADMIN_ID = 6177929931  # Replace with actual Hidden Admin ID

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO  # Set to DEBUG for more verbose output
)

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

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle errors that occur during updates.
    """
    logger.error("An error occurred:", exc_info=context.error)

def main():
    """
    Main function to initialize the delete bot and register handlers.
    """
    TOKEN = os.getenv('DELETE_BOT_TOKEN')
    if not TOKEN:
        logger.error("⚠️ DELETE_BOT_TOKEN is not set.")
        sys.exit("⚠️ DELETE_BOT_TOKEN is not set.")
    TOKEN = TOKEN.strip()
    if TOKEN.lower().startswith('bot='):
        TOKEN = TOKEN[len('bot='):].strip()
        logger.warning("DELETE_BOT_TOKEN should not include 'bot=' prefix. Stripping it.")

    try:
        application = ApplicationBuilder().token(TOKEN).build()
    except Exception as e:
        logger.critical(f"Failed to build the delete application with the provided TOKEN: {e}")
        sys.exit(f"Failed to build the delete application with the provided TOKEN: {e}")

    # Register command handlers
    application.add_handler(CommandHandler("be_sad", be_sad_cmd))
    application.add_handler(CommandHandler("be_happy", be_happy_cmd))

    # Register error handler
    application.add_error_handler(error_handler)

    logger.info("🚀 Delete Bot starting...")
    try:
        application.run_polling()
    except Exception as e:
        logger.critical(f"Delete Bot encountered a critical error and is shutting down: {e}")
        sys.exit(f"Delete Bot encountered a critical error and is shutting down: {e}")

if __name__ == '__main__':
    main()

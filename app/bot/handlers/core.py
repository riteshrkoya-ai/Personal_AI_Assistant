from telegram import Update
from telegram.ext import ContextTypes

from app.bot.keyboards import main_menu_keyboard
from app.bot.state import clear_active_flow


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return

    chat_id = update.effective_chat.id if update.effective_chat else None

    await update.message.reply_text(
        "AI Personal Assistant bot is running.\n\n"
        f"Your Telegram chat ID is: {chat_id}\n\n"
        "Use /menu to open the interactive assistant menu.",
        reply_markup=main_menu_keyboard(),
    )


async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return

    chat_id = update.effective_chat.id if update.effective_chat else None

    await update.message.reply_text(
        f"Your Telegram chat ID is: {chat_id}"
    )


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return

    clear_active_flow(context)

    await update.message.reply_text(
        "What would you like to do?",
        reply_markup=main_menu_keyboard(),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return

    await update.message.reply_text(
        "You can use the assistant in two ways:\n\n"
        "1. Tap buttons from /menu\n"
        "2. Use shortcut commands if you prefer typing\n\n"
        "Useful shortcuts:\n"
        "/remember <text>\n"
        "/memories\n"
        "/memorysearch <query>\n"
        "/forget - choose a memory to delete\n"
        "/remind YYYY-MM-DD HH:MM <message>\n"
        "/reminders\n"
        "/cancelreminder - choose a reminder to cancel",
        reply_markup=main_menu_keyboard(),
    )
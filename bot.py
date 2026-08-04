import os
import asyncio
import subprocess
import tempfile
import logging
import signal
import time
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# ========== HARDCODED TOKEN (as requested) ==========
TOKEN = "8981863184:AAFc5_NqMUx6y04kc3niCbA5Aj1o5mi5JSU"

# ========== LOGGING ==========
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========== SECURITY BLOCKLIST ==========
BLOCKED_KEYWORDS = [
    "os.", "subprocess", "__import__", "eval", "exec",
    "compile", "open(", "file(", "system(", "popen",
    "globals", "locals", "getattr", "setattr", "delattr",
    "__builtins__", "__dict__", "__class__", "__bases__",
    "__subclasses__", "__mro__", "__code__", "__call__"
]

# ========== COMMAND: /start ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📘 Docs", url="https://docs.python.org/3/")],
        [InlineKeyboardButton("🐞 Report Bug", callback_data="bug")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🧠 **𝙿𝚘𝚝𝚊𝚝𝚘 𝙲𝚘𝚍𝚎 𝙴𝚡𝚎𝚌𝚞𝚝𝚘𝚛 𝚟𝟹.𝟶**\n\n"
        "𝙼𝚊𝚒𝚗 𝚢𝚑𝚊𝚗 𝚑𝚞𝚗 𝚝𝚞𝚖𝚑𝚊𝚛𝚒 𝙿𝚢𝚝𝚑𝚘𝚗 𝚌𝚘𝚍𝚎 𝚜𝚊𝚏𝚎𝚕𝚢 𝚛𝚞𝚗 𝚔𝚊𝚛𝚗𝚎 𝚔𝚎 𝚕𝚒𝚢𝚎.\n"
        "𝚂𝚒𝚛𝚏 `/𝚛𝚞𝚗 <𝚢𝚘𝚞𝚛_𝚌𝚘𝚍𝚎>` 𝚋𝚑𝚎𝚓𝚘.\n"
        "𝚃𝚒𝚖𝚎𝚘𝚞𝚝: 𝟻 𝚜𝚎𝚔.\n"
        "𝙱𝚕𝚘𝚌𝚔𝚕𝚒𝚜𝚝: 𝚘𝚜, 𝚜𝚞𝚋𝚙𝚛𝚘𝚌𝚎𝚜𝚜, 𝚎𝚟𝚊𝚕, 𝚎𝚝𝚌.\n\n"
        "🔥 𝙱𝚢 𝙿𝚘𝚝𝚊𝚝𝚘 𝚃𝚑𝚎 𝙻𝚎𝚐𝚎𝚗𝚍",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# ========== BUTTON CALLBACK ==========
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "bug":
        await query.edit_message_text("🐞 𝙱𝚞𝚐 𝚛𝚎𝚙𝚘𝚛𝚝 𝚏𝚎𝚊𝚝𝚞𝚛𝚎 𝚌𝚘𝚖𝚒𝚗𝚐 𝚜𝚘𝚘𝚗! 𝙰𝚋𝚑𝚒 𝚋𝚊𝚜 𝚖𝚞𝚓𝚑𝚎 𝙳𝙼 𝚔𝚊𝚛𝚘 @𝙿𝚘𝚝𝚊𝚝𝚘𝙻𝚎𝚐𝚎𝚗𝚍")

# ========== SANITY CHECK ==========
def is_safe(code: str) -> bool:
    code_lower = code.lower()
    for kw in BLOCKED_KEYWORDS:
        if kw in code_lower:
            return False
    return True

# ========== COMMAND: /run ==========
async def run_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text.startswith("/run"):
        code = text[4:].strip()
    else:
        code = text.strip()

    if not code:
        await update.message.reply_text("❌ 𝙺𝚘𝚒 𝚌𝚘𝚍𝚎 𝚗𝚑𝚒 𝚍𝚒𝚢𝚊. /𝚛𝚞𝚗 𝚙𝚢𝚝𝚑𝚘𝚗_𝚌𝚘𝚍𝚎")
        return

    if not is_safe(code):
        await update.message.reply_text("⛔ 𝙱𝚕𝚘𝚌𝚔𝚎𝚍! 𝙳𝚊𝚗𝚐𝚎𝚛𝚘𝚞𝚜 𝚔𝚎𝚢𝚠𝚘𝚛𝚍 𝚍𝚎𝚝𝚎𝚌𝚝𝚎𝚍.")
        return

    # Send "typing" status
    await update.message.chat.send_action(action="typing")

    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            tmp_path = f.name

        # Run with timeout using asyncio
        proc = await asyncio.create_subprocess_exec(
            'python', tmp_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            os.remove(tmp_path)
            await update.message.reply_text("⏰ 𝚃𝚒𝚖𝚎𝚘𝚞𝚝! 𝙲𝚘𝚍𝚎 𝟻 𝚜𝚎𝚔 𝚜𝚎 𝚣𝚢𝚊𝚍𝚊 𝚌𝚑𝚕𝚊.")
            return

        os.remove(tmp_path)

        output = stdout.decode('utf-8', errors='replace').strip()
        error = stderr.decode('utf-8', errors='replace').strip()

        if error:
            # Truncate if too long
            if len(error) > 4000:
                error = error[:3997] + "..."
            await update.message.reply_text(f"⚠️ **𝙴𝚛𝚛𝚘𝚛:**\n```\n{error}\n```", parse_mode='Markdown')
        else:
            if not output:
                output = "✅ 𝙲𝚘𝚍𝚎 𝚎𝚡𝚎𝚌𝚞𝚝𝚎𝚍 𝚜𝚞𝚌𝚌𝚎𝚜𝚜𝚏𝚞𝚕𝚕𝚢 (𝚗𝚘 𝚘𝚞𝚝𝚙𝚞𝚝)."
            if len(output) > 4000:
                output = output[:3997] + "..."
            await update.message.reply_text(f"📤 **𝙾𝚞𝚝𝚙𝚞𝚝:**\n```\n{output}\n```", parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Run error: {e}")
        await update.message.reply_text(f"💥 𝙸𝚗𝚝𝚎𝚛𝚗𝚊𝚕 𝚎𝚛𝚛𝚘𝚛: {str(e)}")

# ========== HANDLE PLAIN TEXT (without /run) ==========
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # If it's not a command, treat as code
    if update.message.text and not update.message.text.startswith('/'):
        await run_code(update, context)

# ========== ERROR HANDLER ==========
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")
    if update and update.message:
        await update.message.reply_text("⚠️ 𝚂𝚘𝚖𝚎𝚝𝚑𝚒𝚗𝚐 𝚠𝚎𝚗𝚝 𝚠𝚛𝚘𝚗𝚐. 𝙿𝚕𝚎𝚊𝚜𝚎 𝚝𝚛𝚢 𝚊𝚐𝚊𝚒𝚗.")

# ========== MAIN ==========
def main():
    # Build application with proper settings
    app = Application.builder().token(TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("run", run_code))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(button_callback))

    # Error handler
    app.add_error_handler(error_handler)

    # Start polling with retry logic
    logger.info("🚀 𝙱𝚘𝚝 𝚜𝚝𝚊𝚛𝚝𝚒𝚗𝚐...")
    app.run_polling(
        drop_pending_updates=True,  # Avoid 409 conflict
        allowed_updates=Update.ALL_TYPES
    )

if __name__ == "__main__":
    main()

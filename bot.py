import os
import requests
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# ========== HARDCODED TOKEN ==========
BOT_TOKEN = "8981863184:AAFc5_NqMUx6y04kc3niCbA5Aj1o5mi5JSU"
SERVER_URL = "https://your-railway-app.railway.app"  # CHANGE THIS AFTER DEPLOY

logging.basicConfig(level=logging.INFO)

# ========== COMMANDS ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📤 Upload .py", callback_data="upload")],
        [InlineKeyboardButton("📜 History", callback_data="history")],
        [InlineKeyboardButton("🏠 Home", url=SERVER_URL)],
        [InlineKeyboardButton("📘 Docs", url="https://docs.python.org/3/")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🚀 **𝙿𝙾𝚃𝙰𝚃𝙾 𝙵𝚁𝙴𝙴 𝙲𝙾𝙳𝙴 𝙷𝙾𝚂𝚃𝙸𝙽𝙶**\n\n"
        "𝙲𝚘𝚖𝚖𝚊𝚗𝚍𝚜:\n"
        "/run <code> - 𝙴𝚡𝚎𝚌𝚞𝚝𝚎 𝚌𝚘𝚍𝚎\n"
        "/upload - 𝚄𝚙𝚕𝚘𝚊𝚍 𝚊 .𝚙𝚢 𝚏𝚒𝚕𝚎\n"
        "/history - 𝚂𝚎𝚎 𝚙𝚊𝚜𝚝 𝚛𝚞𝚗𝚜\n"
        "/get <id> - 𝙶𝚎𝚝 𝚌𝚘𝚍𝚎 𝚍𝚎𝚝𝚊𝚒𝚕𝚜\n"
        "/delete <id> - 𝙳𝚎𝚕𝚎𝚝𝚎 𝚊 𝚌𝚘𝚍𝚎\n\n"
        "🆓 𝙵𝚁𝙴𝙴 & 𝚄𝙽𝙻𝙸𝙼𝙸𝚃𝙴𝙳 𝙷𝙾𝚂𝚃𝙸𝙽𝙶",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def run_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    code = text.replace('/run', '').strip()

    if not code:
        await update.message.reply_text("❌ 𝙲𝚘𝚍𝚎 𝚍𝚘 𝚗𝚊𝚑𝚒! /𝚛𝚞𝚗 𝚙𝚛𝚒𝚗𝚝('𝚑𝚎𝚕𝚕𝚘')")
        return

    # Send to server
    try:
        resp = requests.post(f"{SERVER_URL}/run", json={"code": code, "timeout": 10}, timeout=15)
        data = resp.json()

        if data.get('error'):
            await update.message.reply_text(f"⚠️ **𝙴𝚛𝚛𝚘𝚛:**\n```\n{data['error']}\n```", parse_mode='Markdown')
        else:
            out = data.get('output', '(no output)')
            if len(out) > 4000:
                out = out[:3997] + "..."
            await update.message.reply_text(f"📤 **𝙾𝚞𝚝𝚙𝚞𝚝:**\n```\n{out}\n```\n🆔 `{data['id']}`", parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"💥 𝙴𝚛𝚛𝚘𝚛: {str(e)}")

async def upload_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📤 𝙿𝚕𝚎𝚊𝚜𝚎 𝚜𝚎𝚗𝚍 𝚊 .𝚙𝚢 𝚏𝚒𝚕𝚎 𝚊𝚜 𝚍𝚘𝚌𝚞𝚖𝚎𝚗𝚝.")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc.file_name.endswith('.py'):
        await update.message.reply_text("❌ 𝚂𝚒𝚛𝚏 .𝚙𝚢 𝚏𝚒𝚕𝚎𝚜 𝚊𝚕𝚕𝚘𝚠𝚎𝚍")
        return

    file = await doc.get_file()
    file_content = await file.download_as_bytearray()
    code = file_content.decode('utf-8')

    try:
        resp = requests.post(f"{SERVER_URL}/upload", files={"file": (doc.file_name, code)}, timeout=20)
        data = resp.json()

        if data.get('error'):
            await update.message.reply_text(f"⚠️ 𝙴𝚛𝚛𝚘𝚛: {data['error']}")
        else:
            out = data.get('output', '(no output)')
            if len(out) > 4000:
                out = out[:3997] + "..."
            await update.message.reply_text(
                f"✅ **𝚄𝚙𝚕𝚘𝚊𝚍𝚎𝚍 & 𝙴𝚡𝚎𝚌𝚞𝚝𝚎𝚍**\n🆔 `{data['id']}`\n📤 𝙾𝚞𝚝𝚙𝚞𝚝:\n```\n{out}\n```",
                parse_mode='Markdown'
            )
    except Exception as e:
        await update.message.reply_text(f"💥 𝙴𝚛𝚛𝚘𝚛: {str(e)}")

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        resp = requests.get(f"{SERVER_URL}/history", timeout=10)
        data = resp.json()
        if not data:
            await update.message.reply_text("📭 𝙽𝚘 𝚑𝚒𝚜𝚝𝚘𝚛𝚢 𝚢𝚎𝚝.")
            return

        msg = "📜 **𝙻𝚊𝚜𝚝 𝟷𝟶𝟶 𝚎𝚡𝚎𝚌𝚞𝚝𝚒𝚘𝚗𝚜:**\n\n"
        for item in data[:20]:
            msg += f"🆔 `{item['id']}` | {item['filename']} | {item['status']} | {item['created_at'][:10]}\n"

        await update.message.reply_text(msg, parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"💥 𝙴𝚛𝚛𝚘𝚛: {str(e)}")

async def get_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    parts = update.message.text.split()
    if len(parts) < 2:
        await update.message.reply_text("❌ /𝚐𝚎𝚝 <𝚒𝚍>")
        return

    code_id = parts[1]
    try:
        resp = requests.get(f"{SERVER_URL}/code/{code_id}", timeout=10)
        data = resp.json()
        if data.get('error'):
            await update.message.reply_text(f"❌ {data['error']}")
            return

        msg = f"🆔 **{data['id']}**\n📁 {data['filename']}\n📅 {data['created_at']}\n📊 𝚂𝚝𝚊𝚝𝚞𝚜: {data['status']}\n\n📤 𝙾𝚞𝚝𝚙𝚞𝚝:\n```\n{data['output'][:2000]}\n```"
        await update.message.reply_text(msg, parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"💥 {str(e)}")

async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    parts = update.message.text.split()
    if len(parts) < 2:
        await update.message.reply_text("❌ /𝚍𝚎𝚕𝚎𝚝𝚎 <𝚒𝚍>")
        return

    code_id = parts[1]
    try:
        resp = requests.delete(f"{SERVER_URL}/delete/{code_id}", timeout=10)
        if resp.status_code == 200:
            await update.message.reply_text(f"✅ 𝙳𝚎𝚕𝚎𝚝𝚎𝚍 `{code_id}`", parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ 𝙽𝚘𝚝 𝚏𝚘𝚞𝚗𝚍")
    except Exception as e:
        await update.message.reply_text(f"💥 {str(e)}")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "upload":
        await query.edit_message_text("📤 𝙿𝚕𝚎𝚊𝚜𝚎 𝚜𝚎𝚗𝚍 𝚊 .𝚙𝚢 𝚏𝚒𝚕𝚎.")
    elif query.data == "history":
        await history_command(update, context)

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("run", run_command))
    app.add_handler(CommandHandler("upload", upload_command))
    app.add_handler(CommandHandler("history", history_command))
    app.add_handler(CommandHandler("get", get_command))
    app.add_handler(CommandHandler("delete", delete_command))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(CallbackQueryHandler(button_callback))

    print("🚀 Bot running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

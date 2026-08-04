import os, requests, logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

BOT_TOKEN = "8981863184:AAFc5_NqMUx6y04kc3niCbA5Aj1o5mi5JSU"
SERVER_URL = "https://your-railway-app.railway.app"  # CHANGE THIS

logging.basicConfig(level=logging.INFO)

async def start(update, context):
    keyboard = [
        [InlineKeyboardButton("📤 Upload .py", callback_data="upload")],
        [InlineKeyboardButton("📜 History", callback_data="history")],
        [InlineKeyboardButton("🏠 Server", url=SERVER_URL)]
    ]
    await update.message.reply_text(
        "🚀 **𝙿𝙾𝚃𝙰𝚃𝙾 𝙵𝚁𝙴𝙴 𝙲𝙾𝙳𝙴 𝙷𝙾𝚂𝚃𝙸𝙽𝙶**\n\n"
        "/run <code> - 𝙴𝚡𝚎𝚌𝚞𝚝𝚎 𝚌𝚘𝚍𝚎\n"
        "/upload - 𝚄𝚙𝚕𝚘𝚊𝚍 .𝚙𝚢 𝚏𝚒𝚕𝚎\n"
        "/history - 𝚂𝚎𝚎 𝚙𝚊𝚜𝚝 𝚛𝚞𝚗𝚜\n"
        "/get <id> - 𝙶𝚎𝚝 𝚍𝚎𝚝𝚊𝚒𝚕𝚜\n"
        "/delete <id> - 𝙳𝚎𝚕𝚎𝚝𝚎\n\n"
        "🆓 𝙵𝚁𝙴𝙴 + 𝚄𝙽𝙻𝙸𝙼𝙸𝚃𝙴𝙳",
        reply_markup=keyboard, parse_mode='Markdown'
    )

async def run_command(update, context):
    code = update.message.text.replace('/run', '').strip()
    if not code:
        await update.message.reply_text("❌ /run print('hello')")
        return
    try:
        resp = requests.post(f"{SERVER_URL}/run", json={"code": code}, timeout=15)
        data = resp.json()
        if data.get('error'):
            await update.message.reply_text(f"⚠️ Error:\n{data['error']}")
        else:
            out = data.get('output', '')[:4000]
            await update.message.reply_text(f"📤 Output:\n```\n{out}\n```\n🆔 {data['id']}", parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"💥 {str(e)}")

async def upload_command(update, context):
    await update.message.reply_text("📤 Send a .py file as document.")

async def handle_document(update, context):
    doc = update.message.document
    if not doc.file_name.endswith('.py'):
        await update.message.reply_text("❌ Only .py files")
        return
    file = await doc.get_file()
    code = (await file.download_as_bytearray()).decode('utf-8')
    try:
        resp = requests.post(f"{SERVER_URL}/upload", files={"file": (doc.file_name, code)}, timeout=20)
        data = resp.json()
        if data.get('error'):
            await update.message.reply_text(f"⚠️ {data['error']}")
        else:
            out = data.get('output', '')[:4000]
            await update.message.reply_text(f"✅ Uploaded\n🆔 {data['id']}\nOutput:\n```\n{out}\n```", parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"💥 {str(e)}")

async def history_command(update, context):
    try:
        resp = requests.get(f"{SERVER_URL}/history", timeout=10)
        data = resp.json()
        if not data:
            await update.message.reply_text("📭 No history")
            return
        msg = "📜 Last 100 runs:\n"
        for item in data[:20]:
            msg += f"🆔 {item['id']} | {item['filename']} | {item['status']} | {item['created_at'][:10]}\n"
        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f"💥 {str(e)}")

async def get_command(update, context):
    parts = update.message.text.split()
    if len(parts) < 2:
        await update.message.reply_text("❌ /get <id>")
        return
    try:
        resp = requests.get(f"{SERVER_URL}/code/{parts[1]}", timeout=10)
        data = resp.json()
        if data.get('error'):
            await update.message.reply_text(f"❌ {data['error']}")
            return
        await update.message.reply_text(
            f"🆔 {data['id']}\n📁 {data['filename']}\n📅 {data['created_at']}\n📊 {data['status']}\n\n📤 Output:\n```\n{data['output'][:2000]}\n```",
            parse_mode='Markdown'
        )
    except Exception as e:
        await update.message.reply_text(f"💥 {str(e)}")

async def delete_command(update, context):
    parts = update.message.text.split()
    if len(parts) < 2:
        await update.message.reply_text("❌ /delete <id>")
        return
    try:
        requests.delete(f"{SERVER_URL}/delete/{parts[1]}")
        await update.message.reply_text(f"✅ Deleted {parts[1]}")
    except Exception as e:
        await update.message.reply_text(f"💥 {str(e)}")

async def button_callback(update, context):
    query = update.callback_query
    await query.answer()
    if query.data == "upload":
        await query.edit_message_text("📤 Send a .py file now.")
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

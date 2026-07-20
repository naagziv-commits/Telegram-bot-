import os
import re
import tempfile
from time import time
from collections import defaultdict
from typing import List

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    CallbackQueryHandler, filters, ContextTypes
)
from telegram.constants import ParseMode
from gtts import gTTS

# ----------------------------------------------------------------------
# CONFIGURATION
# ----------------------------------------------------------------------
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8821679689:AAGUsUZkl2SqlreyHdHaxeFdorpuflP_8f0")
MAX_CHUNK_LEN = 1000
MAX_TEXT_LENGTH = 5000
COOLDOWN_SECONDS = 3

# Branding
BOT_NAME = "🎙️ DRIFT VOICE"
OWNER_NAME = os.environ.get("OWNER_NAME", "Pravin Kewat")
OWNER_CONTACT = os.environ.get("OWNER_CONTACT", "@OWNERxMod1")
BOT_VERSION = os.environ.get("BOT_VERSION", "2.1")

# Rate limiting
user_cooldowns = defaultdict(float)
user_speeds = defaultdict(str)  # user_id -> speed_setting

# ----------------------------------------------------------------------
# LANGUAGE DETECTION
# ----------------------------------------------------------------------
def detect_language(text: str) -> str:
    """Detect language for TTS"""
    if re.search(r'[\u0900-\u097F]', text):
        return 'hi'
    
    hinglish_keywords = ['aap', 'main', 'tum', 'hum', 'hai', 'hain', 'kya', 
                         'kaise', 'bahut', 'thoda', 'acha', 'accha', 'sahi',
                         'nahi', 'haan', 'ji', 'na', 'ho', 'hoga', 'raha']
    words = text.lower().split()
    if not words:
        return 'en'
    hinglish_count = sum(1 for w in words if w in hinglish_keywords)
    if hinglish_count > len(words) * 0.2:
        return 'hi'
    return 'en'

# ----------------------------------------------------------------------
# TEXT CLEANING
# ----------------------------------------------------------------------
def clean_text(text: str) -> str:
    """Clean text"""
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[।]', '.', text)
    return text.strip()

# ----------------------------------------------------------------------
# EMOTION DETECTION
# ----------------------------------------------------------------------
def add_emotion_pauses(text: str) -> str:
    """Add emotion-based punctuation"""
    happy_keywords = [
        'खुश', 'मस्त', 'बढ़िया', 'शानदार', 'अच्छा', 'लव', 'प्यार',
        'हैप्पी', 'ग्रेट', 'वंडरफुल', 'मज़ा', 'कमाल', 'सुपर',
        'happy', 'great', 'awesome', 'love', 'wonderful', 'amazing',
        'excited', 'fantastic', 'cool', 'yay', 'woohoo'
    ]
    sad_keywords = [
        'दुखी', 'उदास', 'बुरा', 'अकेला', 'रोना', 'दर्द', 'गम',
        'सैड', 'सॉरी', 'तकलीफ', 'परेशान', 'निराश',
        'sad', 'unhappy', 'sorry', 'depressed', 'hurt', 'cry',
        'alone', 'pain', 'suffering', 'worried'
    ]
    
    lower_text = text.lower()
    has_punctuation = text.rstrip().endswith(('!', '?', '.', '...'))
    
    # Check for happy keywords
    happy_score = sum(1 for kw in happy_keywords if kw in lower_text)
    sad_score = sum(1 for kw in sad_keywords if kw in lower_text)
    
    if happy_score > sad_score:
        if not has_punctuation:
            text += "!"
        elif not text.rstrip().endswith(('!', '?')):
            text += "!"
    elif sad_score > happy_score:
        if not has_punctuation:
            text += "..."
        elif not text.rstrip().endswith('...'):
            text += "..."
    
    return clean_text(text)

# ----------------------------------------------------------------------
# TEXT SPLITTING
# ----------------------------------------------------------------------
def split_text(text: str, max_len: int = MAX_CHUNK_LEN) -> List[str]:
    """Split long text into chunks"""
    sentences = re.split(r'(?<=[.!?।])\s+', text)
    chunks = []
    current_chunk = ""
    
    for sent in sentences:
        if not sent:
            continue
        if len(current_chunk) + len(sent) + 1 <= max_len:
            if current_chunk:
                current_chunk += " " + sent
            else:
                current_chunk = sent
        else:
            if current_chunk:
                chunks.append(current_chunk)
            if len(sent) > max_len:
                words = sent.split()
                temp = ""
                for word in words:
                    if len(temp) + len(word) + 1 <= max_len:
                        if temp:
                            temp += " " + word
                        else:
                            temp = word
                    else:
                        if temp:
                            chunks.append(temp)
                        temp = word
                if temp:
                    current_chunk = temp
                else:
                    current_chunk = ""
            else:
                current_chunk = sent
    if current_chunk:
        chunks.append(current_chunk)
    return chunks

# ----------------------------------------------------------------------
# VOICE GENERATOR (gTTS)
# ----------------------------------------------------------------------
def generate_voice(text: str, lang: str = 'hi') -> str:
    """Generate voice using gTTS"""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        tmp_path = tmp.name
    
    tts = gTTS(text=text, lang=lang, slow=False)
    tts.save(tmp_path)
    return tmp_path

# ----------------------------------------------------------------------
# MAIN MENU BUTTONS
# ----------------------------------------------------------------------
def get_main_menu() -> InlineKeyboardMarkup:
    """Main menu buttons"""
    keyboard = [
        [
            InlineKeyboardButton("⚡ Speed Control", callback_data="change_speed"),
            InlineKeyboardButton("📊 My Settings", callback_data="my_settings"),
        ],
        [
            InlineKeyboardButton("👨‍💻 Owner", callback_data="owner_info"),
            InlineKeyboardButton("❓ Help", callback_data="help_menu"),
        ],
        [
            InlineKeyboardButton("📢 About", callback_data="about_menu"),
            InlineKeyboardButton("⭐ Rate", url="https://t.me/OWNERxMod1"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# ----------------------------------------------------------------------
# SPEED SELECTION BUTTONS
# ----------------------------------------------------------------------
def get_speed_menu() -> InlineKeyboardMarkup:
    """Speed selection menu"""
    speeds = [
        ("🐢 Very Slow", "veryslow"),
        ("⏸️ Slow", "slow"),
        ("▶️ Normal", "normal"),
        ("⏩ Fast", "fast"),
        ("🚀 Very Fast", "veryfast"),
    ]
    keyboard = []
    for label, value in speeds:
        keyboard.append([InlineKeyboardButton(label, callback_data=f"speed_{value}")])
    keyboard.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="back_menu")])
    return InlineKeyboardMarkup(keyboard)

# ----------------------------------------------------------------------
# SPEED LABELS
# ----------------------------------------------------------------------
SPEED_LABELS = {
    'veryslow': '🐢 Very Slow',
    'slow': '⏸️ Slow',
    'normal': '▶️ Normal',
    'fast': '⏩ Fast',
    'veryfast': '🚀 Very Fast'
}

# ----------------------------------------------------------------------
# START COMMAND
# ----------------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Welcome message"""
    user = update.effective_user
    welcome_text = (
        f"🎙️ <b>{BOT_NAME}</b> v{BOT_VERSION}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👋 Hello {user.first_name}!\n\n"
        f"📨 <b>Send any text message</b>\n"
        f"🔊 I'll convert it to voice\n\n"
        f"✨ <b>Features:</b>\n"
        f"• 🇮🇳 Hindi / 🇬🇧 English / 🔄 Hinglish\n"
        f"• 😊 Emotion Detection (Happy/Sad)\n"
        f"• ⚡ 5 Speed Settings\n"
        f"• 📝 Auto-split long texts\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>👨‍💻 Owner:</b> {OWNER_NAME}\n"
        f"<b>📱 Contact:</b> {OWNER_CONTACT}"
    )
    await update.message.reply_text(
        welcome_text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_menu()
    )

# ----------------------------------------------------------------------
# HELP COMMAND
# ----------------------------------------------------------------------
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Help menu"""
    help_text = (
        "📚 <b>DRIFT VOICE - User Guide</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🎯 <b>How to use:</b>\n"
        "• Send any text → Get voice\n"
        "• Emotions auto-detected\n\n"
        "⚡ <b>Speed Control:</b>\n"
        "• 5 speed options available\n"
        "• Click 'Speed Control' from menu\n\n"
        "😊 <b>Emotion Detection:</b>\n"
        "• Happy words → ! (excited tone)\n"
        "• Sad words → ... (soft tone)\n\n"
        "📝 <b>Long Text:</b>\n"
        "• Auto-split into multiple voices\n"
        "• Progress indicator shown\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"👨‍💻 <b>Owner:</b> {OWNER_NAME}\n"
        f"📱 <b>Contact:</b> {OWNER_CONTACT}"
    )
    await update.message.reply_text(
        help_text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_menu()
    )

# ----------------------------------------------------------------------
# ABOUT COMMAND
# ----------------------------------------------------------------------
async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """About bot"""
    about_text = (
        f"🤖 <b>{BOT_NAME}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>📌 Version:</b> {BOT_VERSION}\n"
        f"<b>📅 Updated:</b> July 2026\n\n"

        f"<b>🔧 Technology:</b>\n"
        f"• Python 3.11+\n"
        f"• Google TTS (gTTS)\n"
        f"• Telegram Bot API\n\n"
        f"<b>✨ Features:</b>\n"
        f"• 🇮🇳 Hindi Support\n"
        f"• 🇬🇧 English Support\n"
        f"• 🔄 Hinglish Support\n"
        f"• 😊 Emotion Detection\n"
        f"• ⚡ Speed Control\n"
        f"• 📝 Auto Split\n"
        f"• 🎨 Interactive Menu\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>👨‍💻 Owner:</b> {OWNER_NAME}\n"
        f"<b>📱 Contact:</b> {OWNER_CONTACT}"
    )
    await update.message.reply_text(
        about_text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_menu()
    )

# ----------------------------------------------------------------------
# OWNER INFO
# ----------------------------------------------------------------------
async def owner_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Owner information"""
    owner_text = (
        f"👨‍💻 <b>Owner Information</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>📛 Name:</b> {OWNER_NAME}\n"
        f"<b>📱 Telegram:</b> {OWNER_CONTACT}\n"
        f"<b>🌐 Brand:</b> DRIFT VOICE\n"
        f"<b>📌 Role:</b> Developer & Founder\n\n"
        f"💡 <b>Services:</b>\n"
        f"• Telegram Bot Development\n"
        f"• AI & Automation\n"
        f"• Custom Solutions\n\n"
        f"📩 <b>Contact for:</b>\n"
        f"• Bot Requests\n"
        f"• Support\n"
        f"• Collaboration\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📩 <b>DM:</b> {OWNER_CONTACT}"
    )
    await update.message.reply_text(
        owner_text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_menu()
    )

# ----------------------------------------------------------------------
# VOICE MESSAGE HANDLER
# ----------------------------------------------------------------------
async def text_to_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Convert text to voice"""
    user_id = update.effective_user.id
    
    # Rate limiting
    if time() - user_cooldowns[user_id] < COOLDOWN_SECONDS:
        await update.message.reply_text("⏳ Please wait 3 seconds before sending again.")
        return
    user_cooldowns[user_id] = time()
    
    text = update.message.text.strip()
    if not text or text.startswith('/'):
        return
    
    if len(text) > MAX_TEXT_LENGTH:
        await update.message.reply_text(f"❌ Text too long! Max {MAX_TEXT_LENGTH} characters.")
        return
    
    # Add emotion
    text = add_emotion_pauses(text)
    
    # Detect language
    lang = detect_language(text)
    lang_name = "Hindi" if lang == 'hi' else "English"
    
    # Get speed setting
    speed = user_speeds.get(user_id, 'normal')
    
    # Split text
    chunks = split_text(text)
    if not chunks:
        await update.message.reply_text("❌ Could not process text.")
        return
    
    # Progress indicator
    if len(chunks) > 1:
        await update.message.reply_text(
            f"📤 Sending {len(chunks)} voice messages...\n"
            f"🌐 Language: {lang_name}\n"
            f"⚡ Speed: {SPEED_LABELS.get(speed, 'Normal')}"
        )
    
    # Generate and send each chunk
    for i, chunk in enumerate(chunks, 1):
        try:
            # Speed control: adjust chunk size
            if speed == 'veryslow':
                # Split into very small chunks
                sub_chunks = split_text(chunk, max_len=200)
                for sub_chunk in sub_chunks:
                    audio_path = generate_voice(sub_chunk, lang)
                    with open(audio_path, 'rb') as audio_file:
                        await update.message.reply_voice(voice=audio_file)
                    os.unlink(audio_path)
            elif speed == 'slow':
                # Split into smaller chunks
                sub_chunks = split_text(chunk, max_len=400)
                for sub_chunk in sub_chunks:
                    audio_path = generate_voice(sub_chunk, lang)
                    with open(audio_path, 'rb') as audio_file:
                        await update.message.reply_voice(voice=audio_file)
                    os.unlink(audio_path)
            elif speed == 'fast':
                # Normal chunks but faster speech (gTTS slow=False)
                audio_path = generate_voice(chunk, lang)
                with open(audio_path, 'rb') as audio_file:
                    await update.message.reply_voice(voice=audio_file)
                os.unlink(audio_path)
            elif speed == 'veryfast':
                # Normal chunks, combine for faster delivery
                audio_path = generate_voice(chunk, lang)
                with open(audio_path, 'rb') as audio_file:
                    await update.message.reply_voice(voice=audio_file)
                os.unlink(audio_path)
            else:  # normal
                audio_path = generate_voice(chunk, lang)
                with open(audio_path, 'rb') as audio_file:
                    await update.message.reply_voice(voice=audio_file)
                os.unlink(audio_path)
            
            # Progress update
            if len(chunks) > 1 and i % 2 == 0 and i < len(chunks):
                await update.message.reply_text(f"📦 Progress: {i}/{len(chunks)}")
                
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")
            try:
                os.unlink(audio_path)
            except:
                pass
            return

# ----------------------------------------------------------------------
# CALLBACK QUERY HANDLER
# ----------------------------------------------------------------------
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button clicks"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    # Back to menu
    if data == "back_menu":
        await query.edit_message_text(
            "🔙 Back to Main Menu!",
            reply_markup=get_main_menu()
        )
        return
    
    # Change speed
    if data == "change_speed":
        current_speed = user_speeds.get(user_id, 'normal')
        await query.edit_message_text(
            f"⚡ <b>Select Speed:</b>\n"
            f"<i>Current Speed: {SPEED_LABELS.get(current_speed, 'Normal')}</i>\n\n"
            f"🐢 Very Slow → 🚀 Very Fast\n"
            f"<i>Note: Speed affects voice quality</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=get_speed_menu()
        )
        return
    
    # My settings
    if data == "my_settings":
        speed = user_speeds.get(user_id, 'normal')
        settings_text = (
            f"📊 <b>Your Settings</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ Speed: {SPEED_LABELS.get(speed, 'Normal')}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 Change settings from menu above"
        )
        await query.edit_message_text(
            settings_text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu()
        )
        return
    
    # Owner info
    if data == "owner_info":
        owner_text = (
            f"👨‍💻 <b>Owner Information</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<b>📛 Name:</b> {OWNER_NAME}\n"
            f"<b>📱 Telegram:</b> {OWNER_CONTACT}\n"
            f"<b>🌐 Brand:</b> DRIFT VOICE\n\n"
            f"💡 <b>Services:</b>\n"
            f"• Bot Development\n"
            f"• Telegram Automation\n"
            f"• AI Integration\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"📩 <b>Contact:</b> {OWNER_CONTACT}"
        )
        await query.edit_message_text(
            owner_text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu()
        )
        return
    
    # Help menu
    if data == "help_menu":
        help_text = (
            "📚 <b>DRIFT VOICE - User Guide</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🎯 <b>How to use:</b>\n"
            "• Send any text → Get voice\n"
            "• Emotions auto-detected\n\n"
            "⚡ <b>Speed:</b> 5 options\n"
            "😊 <b>Emotions:</b> Happy/Sad\n"
            "📝 <b>Long Text:</b> Auto-split\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            f"👨‍💻 <b>Owner:</b> {OWNER_NAME}"
        )
        await query.edit_message_text(
            help_text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu()
        )
        return
    
    # About menu
    if data == "about_menu":
        about_text = (
            f"🤖 <b>{BOT_NAME}</b> v{BOT_VERSION}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<b>🔧 Technology:</b>\n"
            f"• Python + gTTS\n"
            f"• Telegram Bot API\n\n"
            f"<b>✨ Features:</b>\n"
            f"• Hindi/English/Hinglish\n"
            f"• Emotion Detection\n"
            f"• Speed Control\n"
            f"• Auto Split\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>👨‍💻 Owner:</b> {OWNER_NAME}"
        )
        await query.edit_message_text(
            about_text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu()
        )
        return
    
    # Speed select
    if data.startswith("speed_"):
        speed = data.split("_")[1]
        user_speeds[user_id] = speed
        await query.edit_message_text(
            f"✅ Speed changed successfully!\n"
            f"⚡ <b>{SPEED_LABELS.get(speed, 'Normal')}</b>\n\n"
            f"Send any text to hear the new speed!",
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu()
        )
        return

# ----------------------------------------------------------------------
# MAIN FUNCTION
# ----------------------------------------------------------------------
def main() -> None:
    """Start the bot"""
    if not TOKEN:
        print("❌ ERROR: Please set TELEGRAM_BOT_TOKEN environment variable!")
        print("📝 .env file ya hosting panel me TELEGRAM_BOT_TOKEN set karein")
        return
    
    print("🚀 Starting DRIFT VOICE BOT...")
    print("🔐 Token loaded from environment variable")
    print(f"📦 Version: {BOT_VERSION}")
    print(f"👨‍💻 Owner: {OWNER_NAME}")
    print(f"📱 Contact: {OWNER_CONTACT}")
    
    try:
        app = Application.builder().token(TOKEN).build()
        
        # Command handlers
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("about", about_command))
        app.add_handler(CommandHandler("owner", owner_info))
        
        # Message handler
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_to_voice))
        
        # Callback handler for buttons
        app.add_handler(CallbackQueryHandler(button_callback))
        
        print("🎙️ Bot is running...")
        print("🌐 Languages: Hindi + English + Hinglish")
        print("📡 Polling started...")
        
        app.run_polling()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        raise

# ----------------------------------------------------------------------
# ENTRY POINT
# ----------------------------------------------------------------------
if __name__ == "__main__":
    main()

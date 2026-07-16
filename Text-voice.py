import os
import re
import tempfile
import asyncio
from time import time
from collections import defaultdict
from typing import List, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    CallbackQueryHandler, filters, ContextTypes
)
from telegram.constants import ParseMode
import edge_tts

# ----------------------------------------------------------------------
# CONFIGURATION
# ----------------------------------------------------------------------
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8821679689:AAGUsUZkl2SqlreyHdHaxeFdorpuflP_8f0")
MAX_CHUNK_LEN = 1000
MAX_TEXT_LENGTH = 5000
COOLDOWN_SECONDS = 3

# Branding
BOT_NAME = "🎙️ DRIFT VOICE"
OWNER_NAME = "Pravin Kewat"
OWNER_CONTACT = "@OWNERxMod1"

# ----------------------------------------------------------------------
# VOICE CONFIGURATION (Edge TTS)
# ----------------------------------------------------------------------
VOICES = {
    "Hindi Female": "hi-IN-SwaraNeural",
    "Hindi Male": "hi-IN-MadhurNeural",
    "Hinglish Female": "en-IN-NeerjaNeural",
    "Hinglish Male": "en-IN-PrabhatNeural",
    "English US Female": "en-US-JennyNeural",
    "English US Male": "en-US-GuyNeural",
    "English UK Female": "en-GB-SoniaNeural",
    "English UK Male": "en-GB-RyanNeural",
    "Japanese Female": "ja-JP-NanamiNeural",
    "Spanish Female": "es-ES-ElviraNeural",
    "French Female": "fr-FR-DeniseNeural",
    "German Female": "de-DE-KatjaNeural",
}

DEFAULT_VOICE = "hi-IN-SwaraNeural"

# User data storage
user_cooldowns = defaultdict(float)
user_voices = defaultdict(str)
user_speeds = defaultdict(str)  # user_id -> speed
user_themes = defaultdict(str)

# ----------------------------------------------------------------------
# LANGUAGE DETECTION
# ----------------------------------------------------------------------
def detect_language(text: str) -> str:
    """Detect language for TTS"""
    if re.search(r'[\u0900-\u097F]', text):
        return 'hi'
    
    hinglish_keywords = ['aap', 'main', 'tum', 'hum', 'hai', 'hain', 'kya', 
                         'kaise', 'bahut', 'thoda', 'acha', 'accha', 'sahi']
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
    """Clean text - remove extra spaces and fix punctuation"""
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
        'happy', 'great', 'awesome', 'love', 'wonderful', 'amazing',
        'excited', 'fantastic', 'cool', 'yay'
    ]
    sad_keywords = [
        'दुखी', 'उदास', 'बुरा', 'अकेला', 'रोना', 'दर्द',
        'sad', 'unhappy', 'sorry', 'depressed', 'hurt', 'cry',
        'alone', 'pain', 'suffering'
    ]
    
    lower_text = text.lower()
    has_punctuation = text.rstrip().endswith(('!', '?', '.', '...'))
    
    if any(kw in lower_text for kw in happy_keywords):
        if not has_punctuation:
            text += "! 😊"
        elif not text.rstrip().endswith('😊'):
            text += " 😊"
    elif any(kw in lower_text for kw in sad_keywords):
        if not has_punctuation:
            text += "... 😔"
        elif not text.rstrip().endswith('😔'):
            text += " 😔"
    
    return clean_text(text)

# ----------------------------------------------------------------------
# TEXT SPLITTING
# ----------------------------------------------------------------------
def split_text(text: str, max_len: int = MAX_CHUNK_LEN) -> List[str]:
    """Split long text into smaller chunks preserving sentences"""
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
# EDGE TTS VOICE GENERATOR
# ----------------------------------------------------------------------
async def generate_voice(text: str, voice_name: str = DEFAULT_VOICE, rate: str = "+0%") -> Optional[str]:
    """Generate voice using Edge TTS"""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
            tmp_path = tmp.name
        
        communicate = edge_tts.Communicate(text, voice_name, rate=rate)
        await communicate.save(tmp_path)
        
        # Check file size (Telegram 50MB limit)
        if os.path.getsize(tmp_path) > 50 * 1024 * 1024:
            os.unlink(tmp_path)
            return None
        
        return tmp_path
    except Exception as e:
        print(f"❌ TTS Error: {e}")
        return None

# ----------------------------------------------------------------------
# MAIN MENU BUTTONS
# ----------------------------------------------------------------------
def get_main_menu() -> InlineKeyboardMarkup:
    """Main menu buttons"""
    keyboard = [
        [
            InlineKeyboardButton("🎤 Change Voice", callback_data="change_voice"),
            InlineKeyboardButton("⚡ Speed Control", callback_data="change_speed"),
        ],
        [
            InlineKeyboardButton("🎨 Theme", callback_data="change_theme"),
            InlineKeyboardButton("📊 My Settings", callback_data="my_settings"),
        ],
        [
            InlineKeyboardButton("👨‍💻 Owner", callback_data="owner_info"),
            InlineKeyboardButton("❓ Help", callback_data="help_menu"),
        ],
        [
            InlineKeyboardButton("⭐ Rate Bot", url="https://t.me/OWNERxMod1"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# ----------------------------------------------------------------------
# VOICE SELECTION BUTTONS
# ----------------------------------------------------------------------
def get_voice_menu() -> InlineKeyboardMarkup:
    """Voice selection menu"""
    keyboard = []
    row = []
    for i, (name, _) in enumerate(VOICES.items(), 1):
        row.append(InlineKeyboardButton(f"{i}", callback_data=f"voice_{i}"))
        if len(row) == 4:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_menu")])
    return InlineKeyboardMarkup(keyboard)

# ----------------------------------------------------------------------
# SPEED SELECTION BUTTONS
# ----------------------------------------------------------------------
def get_speed_menu() -> InlineKeyboardMarkup:
    """Speed selection menu"""
    speeds = [
        ("🐢 Very Slow", "-50%"),
        ("⏸️ Slow", "-25%"),
        ("▶️ Normal", "+0%"),
        ("⏩ Fast", "+25%"),
        ("🚀 Very Fast", "+50%"),
    ]
    keyboard = []
    for label, value in speeds:
        keyboard.append([InlineKeyboardButton(label, callback_data=f"speed_{value}")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_menu")])
    return InlineKeyboardMarkup(keyboard)

# ----------------------------------------------------------------------
# THEME SELECTION BUTTONS
# ----------------------------------------------------------------------
def get_theme_menu() -> InlineKeyboardMarkup:
    """Theme selection menu"""
    themes = [
        ("🌙 Dark", "dark"),
        ("☀️ Light", "light"),
        ("🌈 Rainbow", "rainbow"),
    ]
    keyboard = []
    for label, value in themes:
        keyboard.append([InlineKeyboardButton(label, callback_data=f"theme_{value}")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_menu")])
    return InlineKeyboardMarkup(keyboard)

# ----------------------------------------------------------------------
# START COMMAND
# ----------------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Welcome message with menu buttons"""
    user = update.effective_user
    welcome_text = (
        f"🎙️ <b>{BOT_NAME}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"👋 Hello {user.first_name}!\n\n"
        f"📨 <b>Send any text message</b>\n"
        f"🔊 I'll convert it to voice\n\n"
        f"✨ <b>Features:</b>\n"
        f"• 400+ Voices (Hindi/English/Hinglish)\n"
        f"• 😊 Emotion Detection\n"
        f"• ⚡ Speed Control\n"
        f"• 🎨 Themes (Dark/Light/Rainbow)\n"
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
        "🎤 <b>Change Voice:</b>\n"
        "• Click 'Change Voice' from menu\n"
        "• Choose from 12+ voices\n\n"
        "⚡ <b>Speed Control:</b>\n"
        "• 5 speed options (Very Slow to Very Fast)\n"
        "• Important text → auto slow\n\n"
        "🎨 <b>Themes:</b>\n"
        "• Dark, Light, Rainbow\n"
        "• Change from menu\n\n"
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
        f"<b>📌 Version:</b> 3.0 (Edge TTS)\n"
        f"<b>🔧 Technology:</b>\n"
        f"• Python + Edge TTS\n"
        f"• 400+ Voice Support\n"
        f"• Hindi/Hinglish/English\n\n"
        f"<b>✨ Features:</b>\n"
        f"• 🎤 Multiple Voices\n"
        f"• ⚡ Speed Control\n"
        f"• 🎨 Themes\n"
        f"• 📊 User Settings\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>👨‍💻 Owner:</b> {OWNER_NAME}\n"
        f"<b>📱 Contact:</b> {OWNER_CONTACT}\n"
        f"<b>⭐ Rate:</b> @OWNERxMod1"
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
        f"<b>🌐 Brand:</b> DRIFT VOICE\n\n"
        f"💡 <b>Services:</b>\n"
        f"• Bot Development\n"
        f"• Telegram Automation\n"
        f"• AI Integration\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📩 <b>Contact:</b> {OWNER_CONTACT}"
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
    
    # User settings
    voice_name = user_voices.get(user_id, DEFAULT_VOICE)
    speed = user_speeds.get(user_id, '+0%')
    
    # Split text
    chunks = split_text(text)
    if not chunks:
        await update.message.reply_text("❌ Could not process text.")
        return
    
    # Progress indicator
    if len(chunks) > 1:
        voice_label = list(VOICES.keys())[list(VOICES.values()).index(voice_name)]
        await update.message.reply_text(
            f"📤 Sending {len(chunks)} voice messages...\n"
            f"🌐 Language: {lang_name}\n"
            f"🎤 Voice: {voice_label}"
        )
    
    # Generate and send each chunk
    for i, chunk in enumerate(chunks, 1):
        audio_path = await generate_voice(chunk, voice_name, speed)
        if not audio_path:
            await update.message.reply_text(f"❌ Chunk {i} generation failed.")
            continue
        
        try:
            with open(audio_path, 'rb') as audio_file:
                caption = f"📝 {i}/{len(chunks)}" if len(chunks) > 1 else None
                await update.message.reply_voice(voice=audio_file, caption=caption)
            os.unlink(audio_path)
            
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
    
    # Change voice
    if data == "change_voice":
        current_voice = user_voices.get(user_id, DEFAULT_VOICE)
        current_label = list(VOICES.keys())[list(VOICES.values()).index(current_voice)]
        await query.edit_message_text(
            f"🎤 <b>Select Voice:</b>\n"
            f"Click the button number to change:\n\n"
            f"<i>Current Voice: {current_label}</i>\n\n"
            f"<b>Available Voices:</b>\n"
            + "\n".join([f"• {i+1}. {name}" for i, name in enumerate(VOICES.keys())]),
            parse_mode=ParseMode.HTML,
            reply_markup=get_voice_menu()
        )
        return
    
    # Change speed
    if data == "change_speed":
        speed = user_speeds.get(user_id, '+0%')
        await query.edit_message_text(
            f"⚡ <b>Select Speed:</b>\n"
            f"<i>Current Speed: {speed}</i>\n\n"
            "🐢 Very Slow → 🚀 Very Fast",
            parse_mode=ParseMode.HTML,
            reply_markup=get_speed_menu()
        )
        return
    
    # Change theme
    if data == "change_theme":
        theme = user_themes.get(user_id, 'light')
        await query.edit_message_text(
            f"🎨 <b>Select Theme:</b>\n"
            f"<i>Current Theme: {theme}</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=get_theme_menu()
        )
        return
    
    # My settings
    if data == "my_settings":
        voice_name = user_voices.get(user_id, DEFAULT_VOICE)
        voice_label = list(VOICES.keys())[list(VOICES.values()).index(voice_name)]
        speed = user_speeds.get(user_id, '+0%')
        theme = user_themes.get(user_id, 'light')
        
        settings_text = (
            f"📊 <b>Your Settings</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎤 Voice: {voice_label}\n"
            f"⚡ Speed: {speed}\n"
            f"🎨 Theme: {theme}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"💡 Change from menu above"
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
            "🎤 <b>Voice:</b> 12+ options\n"
            "⚡ <b>Speed:</b> 5 options\n"
            "🎨 <b>Theme:</b> 3 options"
        )
        await query.edit_message_text(
            help_text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu()
        )
        return
    
    # Voice select
    if data.startswith("voice_"):
        index = int(data.split("_")[1]) - 1
        voice_names = list(VOICES.keys())
        if 0 <= index < len(voice_names):
            selected_voice = voice_names[index]
            voice_value = VOICES[selected_voice]
            user_voices[user_id] = voice_value
            await query.edit_message_text(
                f"✅ Voice changed successfully!\n"
                f"🎤 <b>{selected_voice}</b>\n\n"
                f"Send any text to hear the new voice!",
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
            f"⚡ <b>{speed}</b>\n\n"
            f"Send any text to hear the new speed!",
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu()
        )
        return
    
    # Theme select
    if data.startswith("theme_"):
        theme = data.split("_")[1]
        user_themes[user_id] = theme
        await query.edit_message_text(
            f"✅ Theme changed successfully!\n"
            f"🎨 <b>{theme}</b>\n\n"
            f"<i>Theme will apply on restart</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_menu()
        )
        return

# ----------------------------------------------------------------------
# MAIN FUNCTION
# ----------------------------------------------------------------------
def main() -> None:
    """Start the bot"""
    if not TOKEN or TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ ERROR: Bot token not set!")
        return
    
    # Build application
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
    
    # Start bot
    print("🎙️ DRIFT VOICE BOT STARTED!")
    print("👨‍💻 Owner: Pravin Kewat")
    print("📱 Contact: @OWNERxMod1")
    print("🌐 Languages: Hindi + English + Hinglish")
    print("🎤 400+ Voices (Edge TTS)")
    print("📡 Polling started...")
    
    app.run_polling()

# ----------------------------------------------------------------------
# ENTRY POINT
# ----------------------------------------------------------------------
if __name__ == "__main__":
    main()

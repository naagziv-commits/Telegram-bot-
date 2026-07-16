import os
import re
import tempfile
from time import time
from collections import defaultdict
from typing import List

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from gtts import gTTS

# ----------------------------------------------------------------------
# CONFIGURATION
# ----------------------------------------------------------------------
TOKEN = "8821679689:AAGUsUZkl2SqlreyHdHaxeFdorpuflP_8f0"  # BotFather से अपना टोकन डालें
MAX_CHUNK_LEN = 1000           # प्रति ऑडियो चंक अक्षर (gTTS के लिए सुरक्षित)
MAX_TEXT_LENGTH = 5000         # अधिकतम टेक्स्ट लंबाई
COOLDOWN_SECONDS = 3           # यूज़र कूलडाउन (सेकंड)

# Rate limiting storage
user_cooldowns = defaultdict(float)

# ----------------------------------------------------------------------
# LANGUAGE DETECTION (हिंदी/हिंग्लिश/अंग्रेज़ी)
# ----------------------------------------------------------------------
def detect_language(text: str) -> str:
    """
    भाषा डिटेक्ट करें:
    - 'hi' हिंदी के लिए (देवनागरी या हिंग्लिश)
    - 'en' अंग्रेज़ी के लिए
    """
    # अगर देवनागरी है तो हिंदी
    if re.search(r'[\u0900-\u097F]', text):
        return 'hi'
    
    # हिंग्लिश कीवर्ड (रोमन में लिखी हिंदी)
    hinglish_keywords = [
        'aap', 'main', 'tum', 'hum', 'hai', 'hain', 'kya', 'kaise', 
        'bahut', 'thoda', 'acha', 'accha', 'sahi', 'galat', 'nahi',
        'haan', 'ji', 'na', 'ho', 'hoga', 'raha', 'rahi', 'rahe',
        'sakta', 'sakti', 'sakte', 'chahiye', 'kar', 'karo', 'kare'
    ]
    
    words = text.lower().split()
    if not words:
        return 'en'
    
    hinglish_count = sum(1 for w in words if w in hinglish_keywords)
    # अगर 20% से ज्यादा हिंग्लिश है
    if hinglish_count > len(words) * 0.2:
        return 'hi'
    
    return 'en'

# ----------------------------------------------------------------------
# TEXT CLEANING (हिंदी टेक्स्ट साफ करें)
# ----------------------------------------------------------------------
def clean_text(text: str) -> str:
    """टेक्स्ट को साफ करें - अतिरिक्त स्पेस और विराम चिह्न ठीक करें"""
    # अतिरिक्त स्पेस हटाएं
    text = re.sub(r'\s+', ' ', text)
    # हिंदी पूर्ण विराम को अंग्रेज़ी में बदलें
    text = re.sub(r'[।]', '.', text)
    # हिंदी प्रश्न चिह्न
    text = re.sub(r'[?]', '?', text)
    # हिंदी विस्मयादिबोधक
    text = re.sub(r'[!]', '!', text)
    return text.strip()

# ----------------------------------------------------------------------
# EMOTION & PAUSE ENHANCEMENT (भावना आधारित विराम)
# ----------------------------------------------------------------------
def add_emotion_pauses(text: str) -> str:
    """
    भावना के अनुसार विराम चिह्न और इमोजी जोड़ें
    खुशी = ! 😊, उदासी = ... 😔
    """
    # हिंदी + अंग्रेज़ी हैप्पी कीवर्ड
    happy_keywords = [
        'खुश', 'मस्त', 'बढ़िया', 'शानदार', 'अच्छा', 'लव', 'प्यार',
        'हैप्पी', 'ग्रेट', 'वंडरफुल', 'एक्साइटेड', 'मज़ा', 'धमाका',
        'जिंदाबाद', 'वाह', 'कमाल', 'सुपर', 'फन', 'एंजॉय',
        'happy', 'great', 'awesome', 'love', 'wonderful', 'excited',
        'amazing', 'fantastic', 'cool', 'yay', 'woohoo', 'best'
    ]
    
    # हिंदी + अंग्रेज़ी सैड कीवर्ड
    sad_keywords = [
        'दुखी', 'उदास', 'बुरा', 'अकेला', 'रोना', 'दर्द', 'गम',
        'सैड', 'सॉरी', 'डिप्रेस्ड', 'हर्ट', 'तकलीफ', 'परेशान',
        'निराश', 'मायूस', 'फिक्र', 'चिंता',
        'sad', 'unhappy', 'sorry', 'depressed', 'hurt', 'cry', 'alone',
        'pain', 'suffering', 'worried', 'anxious', 'upset'
    ]
    
    lower_text = text.lower()
    
    # पहले से कोई विराम चिह्न है?
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
# TEXT SPLITTING (वाक्य आधारित टेक्स्ट तोड़ें)
# ----------------------------------------------------------------------
def split_text(text: str, max_len: int = MAX_CHUNK_LEN) -> List[str]:
    """
    लंबे टेक्स्ट को छोटे चंक्स में तोड़ें
    वाक्यों को सुरक्षित रखते हुए
    """
    # हिंदी और अंग्रेज़ी दोनों के लिए
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
            # अगर एक वाक्य भी मैक्स लिमिट से बड़ा है
            if len(sent) > max_len:
                # शब्दों के हिसाब से तोड़ें
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
# GET SPEECH SPEED (भाषण की गति)
# ----------------------------------------------------------------------
def get_speech_speed(text: str) -> bool:
    """
    टेक्स्ट के आधार पर स्पीड तय करें
    True = धीरे, False = सामान्य
    """
    slow_keywords = ['ध्यान', 'गंभीर', 'महत्वपूर्ण', 'careful', 'important',
                     'serious', 'attention', 'सावधान', 'सचेत']
    return any(kw in text.lower() for kw in slow_keywords)

# ----------------------------------------------------------------------
# VOICE MESSAGE HANDLER (मुख्य फंक्शन)
# ----------------------------------------------------------------------
async def text_to_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """टेक्स्ट मैसेज को वॉइस में बदलें और भेजें"""
    
    user_id = update.effective_user.id
    
    # Rate limiting - स्पैम रोकें
    if time() - user_cooldowns[user_id] < COOLDOWN_SECONDS:
        await update.message.reply_text("⏳ थोड़ा रुकें! कृपया कुछ सेकंड बाद फिर भेजें।")
        return
    user_cooldowns[user_id] = time()
    
    # टेक्स्ट प्राप्त करें
    text = update.message.text.strip()
    
    # कमांड को इग्नोर करें (अलग से हैंडल होते हैं)
    if text.startswith('/'):
        return
    
    # खाली टेक्स्ट चेक
    if not text:
        await update.message.reply_text("❌ कृपया वैध टेक्स्ट भेजें।")
        return
    
    # लंबाई की जाँच
    if len(text) > MAX_TEXT_LENGTH:
        await update.message.reply_text(
            f"❌ टेक्स्ट बहुत लंबा है! अधिकतम {MAX_TEXT_LENGTH} अक्षर।\n"
            f"आपके टेक्स्ट में {len(text)} अक्षर हैं।"
        )
        return
    
    # भावना और विराम जोड़ें
    text = add_emotion_pauses(text)
    
    # भाषा डिटेक्ट करें
    lang = detect_language(text)
    lang_name = "हिंदी" if lang == 'hi' else "अंग्रेज़ी"
    
    # टेक्स्ट को चंक्स में तोड़ें
    chunks = split_text(text)
    if not chunks:
        await update.message.reply_text("❌ टेक्स्ट प्रोसेस नहीं हो पाया।")
        return
    
    # प्रोग्रेस इंडिकेटर
    if len(chunks) > 1:
        await update.message.reply_text(
            f"📤 {len(chunks)} वॉइस मैसेज भेज रहा हूँ...\n"
            f"🌐 भाषा: {lang_name}"
        )
    
    # हर चंक के लिए वॉइस जनरेट करें
    for i, chunk in enumerate(chunks, 1):
        try:
            # टेम्पोररी फाइल बनाएं
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
                tmp_path = tmp.name
            
            # स्पीड तय करें
            slow = get_speech_speed(chunk)
            
            # gTTS से वॉइस जनरेट करें
            tts = gTTS(text=chunk, lang=lang, slow=slow)
            tts.save(tmp_path)
            
            # फाइल साइज चेक करें (Telegram की सीमा 50MB)
            file_size = os.path.getsize(tmp_path) / (1024 * 1024)  # MB में
            if file_size > 50:
                await update.message.reply_text(
                    f"⚠️ चंक {i} बहुत बड़ा है ({file_size:.1f}MB)।\n"
                    f"कृपया टेक्स्ट छोटा करें।"
                )
                os.unlink(tmp_path)
                continue
            
            # वॉइस मैसेज भेजें
            with open(tmp_path, 'rb') as audio_file:
                await update.message.reply_voice(
                    voice=audio_file,
                    caption=f"📝 चंक {i}/{len(chunks)}" if len(chunks) > 1 else None
                )
            
            # टेम्पोरेरी फाइल डिलीट करें
            os.unlink(tmp_path)
            
            # प्रोग्रेस अपडेट (हर 2 चंक पर)
            if len(chunks) > 1 and i % 2 == 0 and i < len(chunks):
                await update.message.reply_text(f"📦 प्रोग्रेस: {i}/{len(chunks)}")
                
        except Exception as e:
            error_msg = str(e)
            await update.message.reply_text(
                f"❌ त्रुटि (चंक {i}): {error_msg}\n"
                f"कृपया फिर से प्रयास करें।"
            )
            # फाइल क्लीनअप
            try:
                os.unlink(tmp_path)
            except:
                pass
            return

# ----------------------------------------------------------------------
# START COMMAND (हिंदी में स्वागत)
# ----------------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start कमांड - हिंदी में स्वागत संदेश"""
    welcome_text = (
        "🎙️ <b>DRIFT टेक्स्ट टू वॉइस बॉट</b> <i>लाइव</i>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📨 <b>हिंदी या अंग्रेज़ी में टेक्स्ट भेजें</b> ✍️\n"
        "🔊 <b>वॉइस मैसेज बनेगा</b> 🎧\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "<code>✨ हिंग्लिश | नेचुरल इमोशन | पॉज़ ✨</code>\n\n"
        "🇮🇳 <b>हिंदी, हिंग्लिश और अंग्रेज़ी सपोर्ट</b>\n"
        "😊 <i>खुशी के शब्द → !</i>\n"
        "😔 <i>उदासी के शब्द → ...</i>\n\n"
        "💡 <b>टिप:</b> /help देखें"
    )
    await update.message.reply_text(welcome_text, parse_mode='HTML')

# ----------------------------------------------------------------------
# HELP COMMAND (हिंदी में मदद)
# ----------------------------------------------------------------------
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/help कमांड - उपयोग गाइड"""
    help_text = (
        "📚 <b>कैसे इस्तेमाल करें</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "1️⃣ कोई भी टेक्स्ट भेजें\n"
        "2️⃣ बॉट अपने आप भाषा पहचानेगा\n"
        "3️⃣ वॉइस मैसेज जनरेट होगा\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "🌟 <b>फीचर्स</b>\n"
        "• 🇮🇳 हिंदी / 🇬🇧 अंग्रेज़ी / 🔄 हिंग्लिश\n"
        "• 😊😔 इमोशन डिटेक्शन\n"
        "• 📝 लंबे टेक्स्ट का ऑटो-स्प्लिट\n"
        "• ⏱️ रेट लिमिटिंग (3 सेकंड)\n"
        "• 📊 प्रोग्रेस इंडिकेटर\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 <b>इमोशन कीवर्ड:</b>\n"
        "😊 खुश, बढ़िया, शानदार, love, happy\n"
        "😔 दुखी, उदास, बुरा, sad, sorry\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "⚡ <b>सीमाएं:</b>\n"
        "• अधिकतम {MAX_TEXT_LENGTH} अक्षर\n"
        "• 3 सेकंड का कूलडाउन\n"
        "• 50MB फाइल साइज़ लिमिट\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "<i>❓ किसी भी समस्या के लिए @DriftBotSupport</i>"
    )
    await update.message.reply_text(help_text, parse_mode='HTML')

# ----------------------------------------------------------------------
# ABOUT COMMAND (बॉट की जानकारी)
# ----------------------------------------------------------------------
async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/about - बॉट की जानकारी"""
    about_text = (
        "🤖 <b>DRIFT टेक्स्ट टू वॉइस बॉट</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "📌 <b>वर्शन:</b> 2.0 (हिंदी अपडेट)\n"
        "🔧 <b>टेक्नोलॉजी:</b>\n"
        "• Python + python-telegram-bot\n"
        "• Google Text-to-Speech (gTTS)\n"
        "• हिंदी/हिंग्लिश सपोर्ट\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "👨‍💻 <b>डेवलपर:</b> Drift Tech\n"
        "📅 <b>अपडेट:</b> 15 जुलाई 2026\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "⭐ <i>हिंदी में बोलना अब और आसान!</i>"
    )
    await update.message.reply_text(about_text, parse_mode='HTML')

# ----------------------------------------------------------------------
# MAIN FUNCTION
# ----------------------------------------------------------------------
def main() -> None:
    """बॉट स्टार्ट करें"""
    # टोकन चेक करें
    if TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ ERROR: कृपया अपना बॉट टोकन सेट करें!")
        print("📝 TOKEN = 'YOUR_BOT_TOKEN_HERE' को बदलें")
        return
    
    # Application बनाएं
    app = Application.builder().token(TOKEN).build()
    
    # कमांड हैंडलर
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("about", about_command))
    
    # मैसेज हैंडलर (सिर्फ टेक्स्ट)
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, 
        text_to_voice
    ))
    
    # बॉट स्टार्ट करें
    print("🎙️ DRIFT Text to Voice Bot is running...")
    print("🌐 हिंदी और अंग्रेज़ी सपोर्ट के साथ")
    print("📡 Polling started...")
    
    app.run_polling()

# ----------------------------------------------------------------------
# ENTRY POINT
# ----------------------------------------------------------------------
if __name__ == "__main__":
    main()

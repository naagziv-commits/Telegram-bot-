import os
import requests
import json
import uuid
import time
import threading
import logging
from datetime import datetime
from typing import Optional, Callable, Dict, Any, List
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from telebot.apihelper import ApiTelegramException

# ---------- CONFIG ----------
BOT_TOKEN = "8821679689:AAGUsUZkl2SqlreyHdHaxeFdorpuflP_8f0"  # Direct token

ADMIN_IDS = [7306438851]  # अपना Telegram ID डालो
CONFIG_FILE = "config.json"
COOKIES_FILE = "cookies.json"
LOG_FILE = "bot.log"

logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# ---------- PAYLOAD DEFAULTS ----------
PAYLOAD_CONFIG = {
    "model": "auto",
    "history_and_training_disabled": False,
    "enable_message_followups": True,
    "force_use_sse": True,
    "force_use_search": None,
    "force_paragen": False,
    "supports_buffering": False,
    "timezone": "Africa/Cairo",
    "timezone_offset_min": -180,
    "system_hints": [],
    "is_onboarding_conversation": False,
    "no_auth_ad_preferences": {"personalization_enabled": False, "history_enabled": True},
    "client_prepare_dispatch": "debounced",
    "client_prepare_source": "composer_editor_state",
    "client_prepare_state": "success"
}

PAYLOAD_LABELS = {
    "model": "النموذج",
    "history_and_training_disabled": "تعطيل السجل والتدريب",
    "enable_message_followups": "تفعيل متابعة الرسائل",
    "force_use_sse": "فرض استخدام SSE",
    "force_use_search": "فرض استخدام البحث",
    "force_paragen": "فرض paragen",
    "supports_buffering": "دعم التخزين المؤقت",
    "timezone": "المنطقة الزمنية",
    "timezone_offset_min": "إزاحة المنطقة الزمنية",
    "system_hints": "تلميحات النظام",
    "is_onboarding_conversation": "محادثة تهيئة",
    "no_auth_ad_preferences": "تفضيلات بدون مصادقة",
    "client_prepare_dispatch": "client_prepare_dispatch",
    "client_prepare_source": "client_prepare_source",
    "client_prepare_state": "حالة تحضير العميل"
}

# ---------- CHATGPT CLIENT ----------
class ChatGPT:
    def __init__(self):
        self.session = requests.Session()
        self.payload_config = PAYLOAD_CONFIG.copy()
        self.device_id = None
        self.conduit_token = None
        self.chat_req_token = None
        self.play_integrity_token = None
        self.convo_session_id = None
        self.turn_trace_id = None
        self.base_url = "https://android.chat.openai.com"
        self.prepare_path = "/backend-anon/f/conversation/prepare"
        self.sentinel_path = "/backend-anon/sentinel/chat-requirements"
        self.conversation_path = "/backend-anon/f/conversation"
        self.user_agent = "ChatGPT/1.2026.195 (Android 15; RMX3834; build 2619512)"
        self.device_tier = "lower_mid"
        self.account_id = "default"
        self.residency_region = "no_constraint"
        self.accept_language = "ar-EG,ar;q=0.9,en-US;q=0.8,en;q=0.7"
        self.timezone = "Africa/Cairo"
        self.timezone_offset = -180
        self.sentry_trace = ""
        self.baggage = ""
        self.load_state()
        if not self.device_id:
            self.device_id = str(uuid.uuid4())
            self.save_state()
        self.init_session()

    def load_state(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.device_id = data.get("device_id")
                self.play_integrity_token = data.get("play_integrity_token", "")
                self.conduit_token = data.get("conduit_token", "")
                if "payload_config" in data:
                    for k, v in data["payload_config"].items():
                        if k in self.payload_config:
                            self.payload_config[k] = v
                for attr in ["base_url", "prepare_path", "sentinel_path", "conversation_path",
                             "user_agent", "device_tier", "account_id", "residency_region",
                             "accept_language", "timezone", "timezone_offset"]:
                    if attr in data:
                        setattr(self, attr, data[attr])
                if os.path.exists(COOKIES_FILE):
                    with open(COOKIES_FILE, "r") as f:
                        self.session.cookies.update(json.load(f))
                self.validate_payload_config()
            except Exception as e:
                logging.error(f"Load state error: {e}")

    def validate_payload_config(self):
        valid_states = ["success", "failed", "prepared"]
        if self.payload_config.get("client_prepare_state") not in valid_states:
            self.payload_config["client_prepare_state"] = "success"
        if self.payload_config.get("force_use_search") not in (True, False, None):
            self.payload_config["force_use_search"] = None
        bool_fields = ["history_and_training_disabled", "enable_message_followups",
                       "force_use_sse", "force_paragen", "supports_buffering",
                       "is_onboarding_conversation"]
        for f in bool_fields:
            if not isinstance(self.payload_config.get(f), bool):
                self.payload_config[f] = False
        self.save_state()

    def save_state(self):
        data = {
            "device_id": self.device_id,
            "play_integrity_token": self.play_integrity_token,
            "conduit_token": self.conduit_token,
            "payload_config": self.payload_config,
            "base_url": self.base_url,
            "prepare_path": self.prepare_path,
            "sentinel_path": self.sentinel_path,
            "conversation_path": self.conversation_path,
            "user_agent": self.user_agent,
            "device_tier": self.device_tier,
            "account_id": self.account_id,
            "residency_region": self.residency_region,
            "accept_language": self.accept_language,
            "timezone": self.timezone,
            "timezone_offset": self.timezone_offset
        }
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            with open(COOKIES_FILE, "w") as f:
                json.dump(self.session.cookies.get_dict(), f, indent=2)
        except Exception as e:
            logging.error(f"Save state error: {e}")

    def generate_sentry(self):
        tid = uuid.uuid4().hex
        self.sentry_trace = f"{tid[:16]}-{tid[16:32]}"
        self.baggage = f"sentry-environment=production,sentry-org_id=33249,sentry-public_key=6884768431e4ba548d58cbf3ad96e4ce,sentry-release=com.openai.chatgpt"

    def common_headers(self) -> Dict[str, str]:
        self.generate_sentry()
        return {
            "host": self.base_url.replace("https://", ""),
            "user-agent": self.user_agent,
            "oai-package-name": "com.openai.chatgpt",
            "oai-client-type": "android",
            "oai-device-id": self.device_id,
            "accept-language": self.accept_language,
            "x-device-tier": self.device_tier,
            "chatgpt-account-id": self.account_id,
            "chatgpt-residency-region": self.residency_region,
            "accept": "application/json",
            "sentry-trace": self.sentry_trace,
            "baggage": self.baggage,
            "accept-encoding": "gzip"
        }

    def init_session(self):
        self.convo_session_id = str(uuid.uuid4())
        self.turn_trace_id = str(uuid.uuid4())
        url = f"{self.base_url}{self.prepare_path}"
        headers = self.common_headers()
        headers.update({
            "x-oai-convo-session-id": self.convo_session_id,
            "x-oai-turn-trace-id": self.turn_trace_id,
            "x-conduit-token": self.conduit_token or "",
            "x-openai-target-path": self.prepare_path,
            "content-type": "application/json"
        })
        prepare_body = {
            "action": "next",
            "messages": [],
            "model": self.payload_config["model"],
            "history_and_training_disabled": self.payload_config["history_and_training_disabled"],
            "fork_from_shared_post": False,
            "enable_message_followups": self.payload_config["enable_message_followups"],
            "force_use_sse": self.payload_config["force_use_sse"],
            "force_use_search": self.payload_config["force_use_search"],
            "force_paragen": self.payload_config["force_paragen"],
            "supports_buffering": self.payload_config["supports_buffering"],
            "timezone": self.timezone,
            "timezone_offset_min": self.timezone_offset,
            "system_hints": self.payload_config["system_hints"],
            "is_onboarding_conversation": self.payload_config["is_onboarding_conversation"],
            "no_auth_ad_preferences": self.payload_config["no_auth_ad_preferences"],
            "client_prepare_dispatch": self.payload_config["client_prepare_dispatch"],
            "client_prepare_source": self.payload_config["client_prepare_source"]
        }
        try:
            r = self.session.post(url, headers=headers, json=prepare_body)
            if r.ok and "conduit_token" in r.json():
                self.conduit_token = r.json()["conduit_token"]
                self.save_state()
        except Exception as e:
            logging.error(f"Prepare error: {e}")

        url2 = f"{self.base_url}{self.sentinel_path}"
        headers2 = self.common_headers()
        headers2.update({
            "x-openai-target-path": self.sentinel_path,
            "content-type": "application/json"
        })
        try:
            r = self.session.post(url2, headers=headers2, json={})
            if r.ok:
                self.chat_req_token = r.json().get("token", "")
        except Exception as e:
            logging.error(f"Sentinel error: {e}")
        self.save_state()

    def send_message(self, text: str, conversation_id: Optional[str] = None,
                     parent_id: Optional[str] = None, on_token: Optional[Callable[[str], None]] = None,
                     retry: bool = True):
        url = f"{self.base_url}{self.conversation_path}"
        sentinel = {
            "bot_token": {"play_integrity_token": self.play_integrity_token or ""},
            "chat_requirement_token": self.chat_req_token or ""
        }
        headers = self.common_headers()
        headers.update({
            "accept": "text/event-stream,application/json",
            "cache-control": "no-cache",
            "x-sentinel-payload": json.dumps(sentinel),
            "x-conduit-token": self.conduit_token or "",
            "x-oai-convo-session-id": self.convo_session_id,
            "x-oai-turn-trace-id": str(uuid.uuid4()),
            "x-oai-echo-logs": "1,552,0,822,1,3296,1,5355,0,5533,1,8297,0,8739,1,9818,0,11081,1,12543",
            "x-openai-target-path": self.conversation_path,
            "content-type": "application/json"
        })
        msg_id = str(uuid.uuid4())
        body = {
            "action": "next",
            "messages": [{
                "id": msg_id,
                "author": {"role": "user"},
                "content": {"parts": [text], "content_type": "text"},
                "status": "finished_successfully",
                "recipient": "all",
                "metadata": {"model_slug": self.payload_config["model"],
                             "default_model_slug": "auto"}
            }],
            "model": self.payload_config["model"],
            "history_and_training_disabled": self.payload_config["history_and_training_disabled"],
            "enable_message_followups": self.payload_config["enable_message_followups"],
            "force_use_sse": self.payload_config["force_use_sse"],
            "force_use_search": self.payload_config["force_use_search"],
            "force_paragen": self.payload_config["force_paragen"],
            "supports_buffering": self.payload_config["supports_buffering"],
            "timezone": self.timezone,
            "timezone_offset_min": self.timezone_offset,
            "system_hints": self.payload_config["system_hints"],
            "is_onboarding_conversation": self.payload_config["is_onboarding_conversation"],
            "no_auth_ad_preferences": self.payload_config["no_auth_ad_preferences"],
            "client_prepare_state": self.payload_config["client_prepare_state"],
            "stream": True
        }
        if conversation_id:
            body["conversation_id"] = conversation_id
        if parent_id:
            body["parent_message_id"] = parent_id

        try:
            r = self.session.post(url, headers=headers, json=body, stream=True)
            if r.status_code in (401, 403, 422, 500) and retry:
                self.init_session()
                return self.send_message(text, conversation_id, parent_id, on_token, False)
            r.raise_for_status()
        except Exception as e:
            error_msg = f"Request Exception: {e} | Status: {r.status_code if 'r' in locals() else 'N/A'}"
            logging.error(error_msg)
            return None, None, None, None, error_msg

        if "x-conduit-token" in r.headers:
            self.conduit_token = r.headers["x-conduit-token"]
            self.save_state()

        full_text = ""
        new_conv = conversation_id
        new_parent = parent_id
        model_used = self.payload_config["model"]
        error_msg = None

        try:
            for line in r.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    break
                try:
                    ev = json.loads(data)
                except:
                    continue
                if ev.get("type") == "resume_conversation_token":
                    new_conv = ev.get("conversation_id", new_conv)
                if "message" in ev:
                    m = ev["message"]
                    if m["author"]["role"] == "assistant" and m.get("channel") == "final":
                        new_parent = m["id"]
                        if "metadata" in m and "model_slug" in m["metadata"]:
                            model_used = m["metadata"]["model_slug"]
                        parts = m["content"]["parts"]
                        if parts:
                            cur = "".join(parts)
                            if cur != full_text:
                                new_part = cur[len(full_text):]
                                full_text = cur
                                if on_token:
                                    on_token(new_part)
        except Exception as e:
            error_msg = f"Stream Error: {e}"
            logging.error(error_msg)

        self.save_state()
        return full_text or None, new_conv, new_parent, model_used, error_msg

# ---------- USER SESSIONS ----------
class UserSessions:
    def __init__(self):
        self.sessions: Dict[int, Dict[str, Any]] = {}
        self.timeout = 1800

    def get(self, chat_id: int) -> Dict[str, Any]:
        if chat_id not in self.sessions:
            self.sessions[chat_id] = {
                "conversation_id": None,
                "parent_id": None,
                "history": [],
                "last_active": datetime.now()
            }
        self.sessions[chat_id]["last_active"] = datetime.now()
        return self.sessions[chat_id]

    def reset(self, chat_id: int):
        self.sessions[chat_id] = {
            "conversation_id": None,
            "parent_id": None,
            "history": [],
            "last_active": datetime.now()
        }

    def timeout_check(self):
        now = datetime.now()
        for cid in list(self.sessions.keys()):
            if (now - self.sessions[cid]["last_active"]).total_seconds() > self.timeout:
                del self.sessions[cid]

    def active_count(self) -> int:
        return len(self.sessions)

# ---------- BOT INIT ----------
gpt = ChatGPT()
users = UserSessions()
bot = telebot.TeleBot(BOT_TOKEN)

def auto_saver():
    while True:
        time.sleep(300)
        users.timeout_check()
threading.Thread(target=auto_saver, daemon=True).start()

def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS

def bool_icon(value: bool) -> str:
    return "✅" if value else "❌"

def search_icon(value) -> str:
    if value is True:
        return "✅"
    elif value is False:
        return "❌"
    return "⚪"

def safe_edit_text(text: str, chat_id: int, mid: int, **kwargs):
    try:
        return bot.edit_message_text(text, chat_id, mid, **kwargs)
    except ApiTelegramException as e:
        if "message is not modified" not in str(e):
            raise

# ---------- KEYBOARDS ----------
def main_menu():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("🆕 नई बातचीत", callback_data="new_chat"))
    kb.add(InlineKeyboardButton("📊 सेशन स्थिति", callback_data="session_status"))
    kb.add(InlineKeyboardButton("⚙️ पेलोड सेटिंग", callback_data="payload_menu"))
    return kb

def payload_menu():
    kb = InlineKeyboardMarkup(row_width=2)
    for key, label in PAYLOAD_LABELS.items():
        val = gpt.payload_config.get(key)
        if isinstance(val, bool):
            icon = bool_icon(val)
        elif key == "force_use_search":
            icon = search_icon(val)
        elif isinstance(val, (list, dict)):
            icon = "⚪"
        else:
            icon = f"🔹{val}" if val else "⚪"
        kb.add(InlineKeyboardButton(f"{label}: {icon}", callback_data=f"edit|{key}"))
    kb.add(InlineKeyboardButton("📄 पूरा पेलोड दिखाएं", callback_data="show_payload"))
    kb.add(InlineKeyboardButton("🔙 मुख्य मेनू", callback_data="main_menu"))
    return kb

def boolean_edit_menu(key: str):
    current = gpt.payload_config[key]
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton(f"टॉगल करें (अभी: {bool_icon(current)})", callback_data=f"toggle|{key}"))
    kb.add(InlineKeyboardButton("🔙 वापस", callback_data="payload_menu"))
    return kb

def search_edit_menu(key: str):
    current = gpt.payload_config[key]
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton(f"टॉगल करें (अभी: {search_icon(current)})", callback_data=f"search_toggle|{key}"))
    kb.add(InlineKeyboardButton("🔙 वापस", callback_data="payload_menu"))
    return kb

def model_edit_menu():
    current = gpt.payload_config["model"]
    models = ["auto", "gpt-4o", "gpt-5", "gpt-5-5"]
    kb = InlineKeyboardMarkup(row_width=1)
    for m in models:
        label = f"{'✅ ' if m == current else ''}{m}"
        kb.add(InlineKeyboardButton(label, callback_data=f"model_select|{m}"))
    kb.add(InlineKeyboardButton("🔙 वापस", callback_data="payload_menu"))
    return kb

# ---------- HANDLERS ----------
@bot.message_handler(commands=["start"])
def start_cmd(msg):
    bot.send_message(msg.chat.id,
                     "🤖 *नमस्ते! मैं अनऑफिशियल ChatGPT बॉट हूँ।*\n"
                     "कोई भी टेक्स्ट भेजें, मैं AI मॉडल से जवाब दूंगा।\n"
                     "नियंत्रण के लिए नीचे दिए गए बटनों का उपयोग करें।",
                     parse_mode="Markdown", reply_markup=main_menu())

@bot.message_handler(commands=["new"])
def new_cmd(msg):
    users.reset(msg.chat.id)
    bot.reply_to(msg, "✅ नई बातचीत शुरू हुई।", reply_markup=main_menu())

@bot.message_handler(func=lambda m: True, content_types=['text'])
def handle_text(msg):
    chat_id = msg.chat.id
    text = msg.text.strip()
    if text.startswith("/"):
        return
    session = users.get(chat_id)
    bot.send_chat_action(chat_id, 'typing')
    draft = bot.reply_to(msg, "⏳ सोच रहा हूँ...")
    draft_id = draft.message_id
    full = ""
    last = time.time()

    def on_chunk(chunk: str):
        nonlocal full, last
        full += chunk
        now = time.time()
        if now - last > 0.8 or len(chunk) > 30:
            try:
                bot.edit_message_text(full + "▌", chat_id, draft_id)
                last = now
            except ApiTelegramException:
                pass

    reply, new_cid, new_pid, model, error = gpt.send_message(
        text, session["conversation_id"], session["parent_id"], on_token=on_chunk
    )

    if error:
        if any(str(code) in str(error) for code in ["422", "401", "403"]):
            safe_edit_text("🔄 सेशन रिन्यू कर रहा हूँ, पुनः प्रयास...", chat_id, draft_id)
            gpt.init_session()
            reply2, new_cid2, new_pid2, model2, error2 = gpt.send_message(
                text, session["conversation_id"], session["parent_id"], on_token=on_chunk, retry=False
            )
            if error2:
                safe_edit_text(f"❌ रिन्यू के बाद भी फेल: {error2}", chat_id, draft_id)
            else:
                if reply2 is None:
                    safe_edit_text("❌ कनेक्शन फेल (कोई जवाब नहीं)।", chat_id, draft_id)
                else:
                    try:
                        bot.edit_message_text(reply2, chat_id, draft_id)
                    except ApiTelegramException:
                        bot.delete_message(chat_id, draft_id)
                        bot.send_message(chat_id, reply2, reply_markup=main_menu())
                    session["conversation_id"] = new_cid2
                    session["parent_id"] = new_pid2
                    ts = datetime.now().isoformat()
                    session["history"].append({"role": "user", "content": text, "timestamp": ts})
                    session["history"].append({"role": "assistant", "content": reply2, "model": model2, "timestamp": ts})
            return
        safe_edit_text(f"❌ त्रुटि: {error}", chat_id, draft_id)
        return

    if reply is None:
        safe_edit_text("❌ कनेक्शन फेल (कोई जवाब नहीं)।", chat_id, draft_id)
        return

    try:
        bot.edit_message_text(reply, chat_id, draft_id)
    except ApiTelegramException:
        bot.delete_message(chat_id, draft_id)
        bot.send_message(chat_id, reply, reply_markup=main_menu())

    session["conversation_id"] = new_cid
    session["parent_id"] = new_pid
    ts = datetime.now().isoformat()
    session["history"].append({"role": "user", "content": text, "timestamp": ts})
    session["history"].append({"role": "assistant", "content": reply, "model": model, "timestamp": ts})

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    chat_id = call.message.chat.id
    mid = call.message.message_id
    data = call.data
    uid = call.from_user.id

    admin_actions = ["edit|", "toggle|", "search_toggle|", "model_select|", "payload_menu", "show_payload", "main_menu"]
    if any(data.startswith(p) for p in admin_actions if p.endswith("|") or p in admin_actions):
        if not is_admin(uid):
            bot.answer_callback_query(call.id, "⛔ यह विकल्प केवल एडमिन के लिए", show_alert=True)
            return

    if data == "new_chat":
        users.reset(chat_id)
        safe_edit_text("✅ नई बातचीत तैयार है।", chat_id, mid, reply_markup=main_menu())
        bot.answer_callback_query(call.id)

    elif data == "session_status":
        sess = users.get(chat_id)
        history_len = len(sess["history"])
        active = users.active_count()
        status = f"📊 *सेशन स्थिति*\n"
        status += f"• संदेशों की संख्या: {history_len}\n"
        status += f"• कॉन्वर्सेशन ID: {sess['conversation_id'] or 'कोई नहीं'}\n"
        status += f"• पैरेंट ID: {sess['parent_id'] or 'कोई नहीं'}\n"
        status += f"• सक्रिय सेशन: {active}\n"
        status += f"• वर्तमान मॉडल: {gpt.payload_config['model']}"
        safe_edit_text(status, chat_id, mid, parse_mode="Markdown", reply_markup=main_menu())
        bot.answer_callback_query(call.id)

    elif data == "payload_menu":
        safe_edit_text("⚙️ *पेलोड सेटिंग्स*", chat_id, mid, parse_mode="Markdown", reply_markup=payload_menu())
        bot.answer_callback_query(call.id)

    elif data == "main_menu":
        safe_edit_text("🔙 मुख्य मेनू", chat_id, mid, reply_markup=main_menu())
        bot.answer_callback_query(call.id)

    elif data.startswith("edit|"):
        key = data.split("|")[1]
        val = gpt.payload_config.get(key)
        if isinstance(val, bool):
            safe_edit_text(f"🔘 *{PAYLOAD_LABELS.get(key, key)}*", chat_id, mid, parse_mode="Markdown", reply_markup=boolean_edit_menu(key))
        elif key == "force_use_search":
            safe_edit_text(f"🔍 *{PAYLOAD_LABELS.get(key, key)}*", chat_id, mid, parse_mode="Markdown", reply_markup=search_edit_menu(key))
        elif key == "model":
            safe_edit_text(f"🤖 *मॉडल चुनें*", chat_id, mid, parse_mode="Markdown", reply_markup=model_edit_menu())
        else:
            safe_edit_text(f"📝 *{PAYLOAD_LABELS.get(key, key)}*\nवर्तमान मान: `{val}`\n(इस फ़ील्ड के लिए मैन्युअल संपादन उपलब्ध नहीं)", chat_id, mid, parse_mode="Markdown", reply_markup=payload_menu())
        bot.answer_callback_query(call.id)

    elif data.startswith("toggle|"):
        key = data.split("|")[1]
        if key in gpt.payload_config:
            gpt.payload_config[key] = not gpt.payload_config[key]
            gpt.save_state()
            safe_edit_text(f"🔄 {PAYLOAD_LABELS.get(key, key)} टॉगल किया: {bool_icon(gpt.payload_config[key])}", chat_id, mid, reply_markup=boolean_edit_menu(key))
        bot.answer_callback_query(call.id)

    elif data.startswith("search_toggle|"):
        key = data.split("|")[1]
        if key == "force_use_search":
            current = gpt.payload_config[key]
            if current is None:
                gpt.payload_config[key] = True
            elif current is True:
                gpt.payload_config[key] = False
            else:
                gpt.payload_config[key] = None
            gpt.save_state()
            safe_edit_text(f"🔄 {PAYLOAD_LABELS.get(key, key)} टॉगल किया: {search_icon(gpt.payload_config[key])}", chat_id, mid, reply_markup=search_edit_menu(key))
        bot.answer_callback_query(call.id)

    elif data.startswith("model_select|"):
        model = data.split("|")[1]
        gpt.payload_config["model"] = model
        gpt.save_state()
        safe_edit_text(f"✅ मॉडल चुना: `{model}`", chat_id, mid, parse_mode="Markdown", reply_markup=model_edit_menu())
        bot.answer_callback_query(call.id)

    elif data == "show_payload":
        payload_json = json.dumps(gpt.payload_config, indent=2, ensure_ascii=False)
        if len(payload_json) > 4000:
            payload_json = payload_json[:4000] + "\n... (ट्रंकेटेड)"
        safe_edit_text(f"📄 *वर्तमान पेलोड*\n```json\n{payload_json}\n```", chat_id, mid, parse_mode="Markdown", reply_markup=payload_menu())
        bot.answer_callback_query(call.id)

    else:
        bot.answer_callback_query(call.id, "अज्ञात क्रिया", show_alert=True)

# ---------- START ----------
if __name__ == "__main__":
    print("🚀 बॉट चल रहा है...")
    bot.infinity_polling()

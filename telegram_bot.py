import os
import time
import asyncio
import logging
import requests
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.error import NetworkError, TimedOut
from telegram.constants import ParseMode

# ==========================================
# 1. CONFIGURATION & STATE
# ==========================================

ENGINE_URL = "http://127.0.0.1:8080"

# Telegram Config
BOT_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8ByQmeiguZ3MenAA")
ALLOWED_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "") 

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger("AtmosEyeBot")
CURRENT_TONE = "professional"

# ==========================================
# 2. SECURITY & UTILITIES
# ==========================================

def is_authorized(update: Update) -> bool:
    if not ALLOWED_CHAT_ID: return True
    chat_id = str(update.effective_chat.id if update.effective_chat else update.callback_query.message.chat.id)
    return chat_id == ALLOWED_CHAT_ID

def fetch_api(endpoint: str, method="GET", payload=None):
    url = f"{ENGINE_URL}{endpoint}"
    try:
        if method == "POST": r = requests.post(url, json=payload, timeout=8)
        else: r = requests.get(url, timeout=8)
        if r.status_code == 200: return r.json()
    except Exception as e: logger.error(f"API Error: {e}")
    return None

# ==========================================
# 3. INTERACTIVE KEYBOARDS
# ==========================================

def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("📊 Live Status", callback_data="cmd_status"), InlineKeyboardButton("🧠 AI Insight", callback_data="cmd_insight")],
        [InlineKeyboardButton("💻 System Health", callback_data="cmd_health"), InlineKeyboardButton("🚨 Alert Center", callback_data="cmd_alerts")],
        [InlineKeyboardButton("🌐 Start Tunnel", callback_data="cmd_tunnel_on"), InlineKeyboardButton("🔗 Dashboard Links", callback_data="cmd_dashboard")],
        [InlineKeyboardButton(f"⚙️ Insight Tone: {CURRENT_TONE.capitalize()}", callback_data="cmd_tone_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_tone_menu():
    keyboard = [
        [InlineKeyboardButton("🧪 Scientific", callback_data="tone_scientific"), InlineKeyboardButton("👔 Professional", callback_data="tone_professional")],
        [InlineKeyboardButton("👋 Friendly", callback_data="tone_friendly")],
        [InlineKeyboardButton("⬅️ Back to Home", callback_data="cmd_home")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_refresh_menu(refresh_command: str):
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh Data", callback_data=refresh_command)], [InlineKeyboardButton("⬅️ Back to Home", callback_data="cmd_home")]])

def get_back_menu():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Home", callback_data="cmd_home")]])

# ==========================================
# 4. CORE SCREEN UPDATES
# ==========================================

async def update_screen_status(query):
    data = fetch_api("/api/status")
    if not data:
        await query.edit_message_text("❌ *Engine Offline.*", parse_mode=ParseMode.MARKDOWN, reply_markup=get_back_menu())
        return
    s = data.get('sensors', {})
    t = data.get('trend', {})
    o = data.get('outdoor', {})
    
    # Check if outdoor data exists yet
    outdoor_str = f"🌲 *Outdoor AQI:* `{o.get('aqi', 'N/A')}` | `{o.get('temperature', 'N/A')} °C`\n" if o and o.get('aqi') is None else f"🌲 *Outdoor AQI:* `{o.get('aqi', 'Fetching...')}` | `{o.get('temperature', '...')} °C`\n"
    if o and o.get('aqi'):
        outdoor_str = f"🌲 *Outdoor AQI:* `{o.get('aqi')}` | `{o.get('temperature')} °C`\n"
        
    now = datetime.now().strftime('%H:%M:%S')
    msg = (f"📊 *Live Environmental Status*\n━━━━━━━━━━━━━━━━━━\n"
           f"🌍 *Indoor AQI:* `{data['aqi']['value']}` _{data['aqi']['category']}_\n"
           f"{outdoor_str}"
           f"🌫️ *PM2.5:* `{s.get('pm25')} µg/m³`\n"
           f"🌡️ *Temp:* `{s.get('temperature')} °C`\n"
           f"💧 *Humidity:* `{s.get('humidity')} %`\n"
           f"🏭 *VOC Gas:* `{round(s.get('gas_resistance', 0)/1000, 1)} kΩ`\n"
           f"━━━━━━━━━━━━━━━━━━\n"
           f"📈 *Trend Engine:* {t.get('trend_direction', 'Unknown')}\n"
           f"🛡️ *FSM State:* `{t.get('fsm_state', 'NORMAL')}`\n\n"
           f"🕒 _Updated at {now}_")
    await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=get_refresh_menu("cmd_status"))

async def update_screen_insight(query):
    insight_data = fetch_api(f"/api/insight/refresh?tone={CURRENT_TONE}")
    if not insight_data:
        await query.edit_message_text("❌ *Error generating insight.*", parse_mode=ParseMode.MARKDOWN, reply_markup=get_back_menu())
        return
    now = datetime.now().strftime('%H:%M:%S')
    msg = (f"🧠 *AtmosInsight ({CURRENT_TONE.capitalize()})*\n━━━━━━━━━━━━━━━━━━\n{insight_data.get('insight', 'No summary available.')}\n\n⚠️ *Recommendation:*\n_{insight_data.get('recommendation', 'N/A')}_\n\n🕒 _Generated at {now}_")
    await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=get_refresh_menu("cmd_insight"))

async def update_screen_health(query):
    data = fetch_api("/api/system/info")
    if not data:
        await query.edit_message_text("❌ *Error connecting to Engine.*", parse_mode=ParseMode.MARKDOWN, reply_markup=get_back_menu())
        return
    now = datetime.now().strftime('%H:%M:%S')
    msg = (f"💻 *System Health*\n━━━━━━━━━━━━━━━━━━\n⚙️ *Version:* `{data.get('version')}`\n🧠 *CPU:* `{data.get('cpu')}`\n🗄️ *RAM:* `{data.get('memory')}`\n⏱️ *Uptime:* `{data.get('uptime')}`\n📶 *WiFi:* `{data.get('ssid')}`\n🌐 *IP:* `{data.get('ip')}`\n\n🕒 _Checked at {now}_")
    await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=get_refresh_menu("cmd_health"))

async def update_screen_alerts(query):
    alerts = fetch_api("/api/alerts")
    if alerts is None:
        await query.edit_message_text("❌ *Cannot read alerts.*", parse_mode=ParseMode.MARKDOWN, reply_markup=get_back_menu())
        return
    now = datetime.now().strftime('%H:%M:%S')
    if len(alerts) == 0:
        msg = (f"🚨 *Alert Center*\n━━━━━━━━━━━━━━━━━━\n\n✅ *All Clear*\n_No critical alerts logged._\n\n🕒 _Checked at {now}_")
    else:
        msg = f"🚨 *Alert Center*\n━━━━━━━━━━━━━━━━━━\n\n"
        for a in alerts:
            icon = "🔴" if a['level'] == "critical" else "🔵"
            msg += f"{icon} *{a['time']}*\n_{a['message']}_\n\n"
        msg += f"🕒 _Checked at {now}_"
    await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=get_refresh_menu("cmd_alerts"))

async def update_screen_tunnel(query, action: str):
    if action == "start":
        await query.edit_message_text("🌐 *Initiating Tunnel...*\n⏳ _Negotiating secure node allocation..._", parse_mode=ParseMode.MARKDOWN)
        start_time = time.time()
        res = fetch_api("/api/control/tunnel", method="POST", payload={"action": "start"})
        if not res or not res.get('tunnel'):
            await query.edit_message_text("❌ *Error executing Cloudflared.*", parse_mode=ParseMode.MARKDOWN, reply_markup=get_back_menu())
            return
        tunnel_url = None
        for attempt in range(15):
            await asyncio.sleep(1) 
            status = fetch_api("/api/status")
            if status and status.get("system", {}).get("tunnel"):
                tunnel_url = status["system"]["tunnel"]
                break
        delay = round(time.time() - start_time, 2)
        if tunnel_url:
            msg = f"✅ *Tunnel Activated!*\n⏱️ *Delay:* `{delay}s`\n━━━━━━━━━━━━━━━━━━\n🔗 *Live Dashboard:*\n[Launch Interface]({tunnel_url})"
            await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=get_back_menu())
        else:
            await query.edit_message_text(f"⚠️ *Tunnel mapping timed out.* Check 'Dashboard URL' menu shortly.", parse_mode=ParseMode.MARKDOWN, reply_markup=get_back_menu())
    else:
        fetch_api("/api/control/tunnel", method="POST", payload={"action": "stop"})
        await query.edit_message_text("🛑 *Tunnel Terminated.*", parse_mode=ParseMode.MARKDOWN, reply_markup=get_back_menu())

async def update_screen_dashboard(query):
    status_data = fetch_api("/api/status")
    sys_data = fetch_api("/api/system/info")
    
    if not status_data or not sys_data:
        await query.edit_message_text("❌ Engine not reachable.", reply_markup=get_back_menu())
        return
        
    local_ip = sys_data.get("ip", "127.0.0.1")
    local_url = f"http://{local_ip}:8080"
    tunnel_url = status_data.get("system", {}).get("tunnel")
    
    msg = f"🔗 *AtmosEye Dashboard Links*\n━━━━━━━━━━━━━━━━━━\n\n"
    msg += f"🏠 *Local Network Access:*\n_(Must be on the same Wi-Fi)_\n[👉 Open Local Dashboard]({local_url})\n\n"
    
    if tunnel_url:
        msg += f"🌍 *Remote Cloud Access:*\n_(Works anywhere in the world)_\n[👉 Open Remote Dashboard]({tunnel_url})"
    else:
        msg += f"🔒 *Remote Cloud Access:*\n_Offline (Click 'Start Tunnel' first)_"
        
    await query.edit_message_text(msg, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True, reply_markup=get_back_menu())

async def return_home(query):
    welcome_text = "🌩️ *AtmosEye Control Center*\nSelect an option below to control your device."
    await query.edit_message_text(welcome_text, parse_mode=ParseMode.MARKDOWN, reply_markup=get_main_menu())


# ==========================================
# 5. TELEGRAM ROUTING (HANDLERS)
# ==========================================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update): return
    my_chat_id = update.effective_chat.id
    welcome_text = (f"🌩️ *AtmosEye Control Center*\n\n✅ _Connected. User ID: `{my_chat_id}`_\n\nSelect an option below to control your device:")
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN, reply_markup=get_main_menu())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_authorized(update): return
    data = query.data
    try:
        if data == "cmd_home":
            await return_home(query)
            await query.answer()
        elif data == "cmd_status":
            await update_screen_status(query)
            await query.answer("Fetching live data...")
        elif data == "cmd_insight":
            await query.edit_message_text("🧠 *Thinking... generating AI insight...*", parse_mode=ParseMode.MARKDOWN)
            await update_screen_insight(query)
            await query.answer()
        elif data == "cmd_health":
            await update_screen_health(query)
            await query.answer("Fetching system health...")
        elif data == "cmd_alerts":
            await update_screen_alerts(query)
            await query.answer("Fetching alerts...")
        elif data == "cmd_dashboard":
            await update_screen_dashboard(query)
            await query.answer()
        elif data == "cmd_tunnel_on":
            await query.answer("Starting tunnel...") 
            await update_screen_tunnel(query, "start")
        elif data == "cmd_tunnel_off":
            await update_screen_tunnel(query, "stop")
            await query.answer("Tunnel stopped.")
        elif data == "cmd_tone_menu":
            await query.edit_message_text("⚙️ *Select Insight Tone:*", parse_mode=ParseMode.MARKDOWN, reply_markup=get_tone_menu())
            await query.answer()
        elif data.startswith("tone_"):
            global CURRENT_TONE
            CURRENT_TONE = data.split("_")[1]
            await query.answer(f"Tone set to {CURRENT_TONE}")
            await return_home(query)
    except Exception as e:
        if "Message is not modified" not in str(e): logger.error(f"Button handling error: {e}")

# --- SILENT ERROR HANDLER ---
async def silent_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Silently catches common network timeouts so they don't spam the terminal."""
    if isinstance(context.error, (NetworkError, TimedOut)):
        logger.warning("Telegram network hiccup detected. Automatically retrying...")
    else:
        logger.error(f"Telegram Exception: {context.error}")

# ==========================================
# 6. MAIN LAUNCHER
# ==========================================

def main():
    if not BOT_TOKEN:
        print("[ERROR] TELEGRAM_TOKEN not set.")
        return

    try: import telegram
    except ImportError: return

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .connect_timeout(30.0)
        .read_timeout(30.0)
        .get_updates_connect_timeout(30.0)
        .get_updates_read_timeout(30.0)
        .build()
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("menu", cmd_start))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    # Register the silent error handler
    app.add_error_handler(silent_error_handler)

    print("=============================================")
    print(" AtmosEye Telegram Interface Active")
    print(" UI Engine: High-Speed Command Buttons")
    print("=============================================")
    
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

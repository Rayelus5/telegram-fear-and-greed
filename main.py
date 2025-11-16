import os
import sys
import logging
import time
import requests
from flask import Flask
from waitress import serve
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import threading
from datetime import datetime
import pytz

# ============================================================
# ANTI-DUPLICATE INSTANCE FIX  (MUY IMPORTANTE EN RENDER)
# ============================================================

if os.path.exists(".botlock"):
    print("⚠️ Instancia duplicada detectada. Saliendo para evitar conflicto 409.")
    sys.exit()

open(".botlock", "w").close()


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================
# FLASK APP
# ============================================================

app = Flask(__name__)

@app.route('/health')
def health():
    return {'status': 'ok', 'message': 'Bot is running'}, 200

@app.route('/')
def home():
    return {
        'status': 'Telegram Bot Active - Fear & Greed Monitor',
        'message': 'Use /health for health checks'
    }, 200


# ============================================================
# TELEGRAM SEND
# ============================================================

def send_telegram_message(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
        requests.post(url, data=data)
    except Exception as e:
        logger.error(f"Error enviando mensaje: {e}")


# ============================================================
# FEAR & GREED API
# ============================================================

def get_fear_greed():
    try:
        response = requests.get("https://api.alternative.me/fng/?limit=1")
        fg = response.json()
        value = int(fg["data"][0]["value"])
        classification = fg["data"][0]["value_classification"]
        return value, classification
    except Exception as e:
        logger.error(f"Error consultando Fear & Greed: {e}")
        return None, None


# ============================================================
# DAILY REPORT (09:00 EUROPA/MADRID)
# ============================================================

MADRID_TZ = pytz.timezone("Europe/Madrid")

def send_daily_report():
    value, classification = get_fear_greed()
    if value is None:
        return

    textos = {
        "Extreme Greed":
        "un ambiente de euforia total en los mercados, donde el optimismo reina y las inversiones vuelan alto.",
        "Greed":
        "un clima de entusiasmo y confianza, donde los inversores siguen apostando fuerte.",
        "Neutral":
        "un cielo despejado en el mercado cripto, sin grandes emociones.",
        "Fear":
        "nubes de duda atravesando el mercado, con inversores algo prudentes.",
        "Extreme Fear":
        "una tormenta emocional, donde reina el pánico y los nervios están más tensos que un informático sin café ☕😅"
    }

    clima = textos.get(classification, "un día interesante en los mercados.")

    mensaje = (
        f"🎙️ *Buenos días, estimado espectador cripto* 🌤️\n\n"
        f"Son las *09:00* y comenzamos con el *parte del mercado* 📊\n\n"
        f"El índice *Fear & Greed* marca *{value}/100*, señalando *{classification}*.\n"
        f"Hoy vemos {clima}\n\n"
        f"🌡️ *Índice:* {value}/100\n"
        f"📍 *Sentimiento:* {classification}\n\n"
        f"_Y ahora la dedicatoria del día..._\n\n"
        f"*Papá te quiero* ❤️"
    )

    send_telegram_message(mensaje)


# ============================================================
# TOP 25 CRYPTO (CoinGecko API)
# ============================================================

def get_top25_crypto():
    try:
        url = (
            "https://api.coingecko.com/api/v3/coins/markets"
            "?vs_currency=usd&order=market_cap_desc&per_page=25&page=1&sparkline=false"
        )
        response = requests.get(url, timeout=10)
        data = response.json()

        top_list = []
        for coin in data:
            rank = coin.get("market_cap_rank")
            name = coin.get("name")
            price = coin.get("current_price")
            market_cap = coin.get("market_cap")

            top_list.append(
                f"*#{rank}* — *{name}*\n"
                f"💵 Precio: `${price:,.2f}`\n"
                f"🏦 Market Cap: `${market_cap:,.0f}`\n"
            )

        return "\n".join(top_list)

    except Exception as e:
        logger.error(f"Error obteniendo top 25 crypto: {e}")
        return "❌ Error obteniendo datos del Top 25."



# ============================================================
# DAILY SCHEDULER  → NOW WITH MADRID TIME
# ============================================================

def daily_scheduler():
    already_sent = False
    while True:
        now = datetime.now(MADRID_TZ)

        if now.hour == 9 and now.minute == 0:
            if not already_sent:
                send_daily_report()
                already_sent = True

        elif now.hour != 9:
            already_sent = False

        time.sleep(20)


# ============================================================
# COMMANDS
# ============================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Bot Fear & Greed activo*\n\n"
        "Te aviso cuando:\n"
        "• Índice > 75 → Codicia extrema\n"
        "• Índice < 25 → Miedo extremo\n"
        "• Todos los días a las 09:00 (Madrid) → Informe diario\n\n"
        "Comandos:\n"
        "/top25 → Ver ranking crypto\n"
        "/check → Ver índice actual\n"
        "/status → Estado del bot",
        parse_mode="Markdown")


async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value, classification = get_fear_greed()
    if value is None:
        await update.message.reply_text("Error obteniendo datos.")
        return

    await update.message.reply_text(
        f"📊 *Fear & Greed*\n\nValor: *{value}/100*\nSentimiento: *{classification}*",
        parse_mode="Markdown")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot funcionando correctamente.")


async def top25_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Obteniendo top 25 criptomonedas...")

    lista = get_top25_crypto()

    await update.message.reply_text(
        f"📊 *TOP 25 CRIPTOS POR CAPITALIZACIÓN*\n\n{lista}",
        parse_mode="Markdown"
    )


# ============================================================
# THREADS & BOOT
# ============================================================

def run_flask():
    serve(app, host='0.0.0.0', port=5000)


def run_bot():
    global BOT_TOKEN, CHAT_ID

    BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

    if not BOT_TOKEN or not CHAT_ID:
        print("❌ ERROR: TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID no configurados en Render.")
        sys.exit()

    app_bot = Application.builder().token(BOT_TOKEN).build()
    app_bot.add_handler(CommandHandler("start", start_command))
    app_bot.add_handler(CommandHandler("check", check_command))
    app_bot.add_handler(CommandHandler("status", status_command))
    app_bot.add_handler(CommandHandler("top25", top25_command))

    print("Bot polling iniciado...")
    app_bot.run_polling()


# ============================================================
# START
# ============================================================

if __name__ == '__main__':
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    daily_thread = threading.Thread(target=daily_scheduler, daemon=True)
    daily_thread.start()

    run_bot()

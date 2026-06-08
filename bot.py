import time
import os
import requests
import pandas as pd
import numpy as np
import sys
import threading
import logging
from datetime import datetime, timezone

from strategy import get_trend_signal
from iqoptionapi.stable_api import IQ_Option

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ==========================================
# ⚙️ CONFIGURACIÓN - LISTA AMPLIADA DE PARES
# ==========================================
EMAIL = os.getenv("IQ_EMAIL")
PASSWORD = os.getenv("IQ_PASSWORD")
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

EXPIRATION = 1
BASE_AMOUNT = 25
TIMEFRAME_M1 = 60

# ✅ LISTA AMPLIADA A 16 PARES (OTC + REAL)
PAIRS = [
    "EURUSD-OTC", "GBPUSD-OTC", "USDCHF-OTC", "USDJPY-OTC",
    "EURGBP-OTC", "EURJPY-OTC", "GBPJPY-OTC", "AUDUSD-OTC",
    "USDCAD-OTC", "NZDUSD-OTC", "AUDJPY-OTC", "CADJPY-OTC",
    "GBPAUD-OTC", "EURAUD-OTC", "AUDCAD-OTC", "NZDJPY-OTC"
]

MAX_DAILY_TRADES = 50       # Más límite por tener más activos
MAX_LOSS_STREAK = 3
PAUSE_TIME = 1800
MAX_RECONNECT_ATTEMPTS = 5
RECONNECT_DELAY = 5
FUERZA_MINIMA = 62          # Umbral un poco más bajo para más señales

# Variables globales
DAILY_TRADES = 0
CURRENT_DAY = datetime.now(timezone.utc).day
LOSS_STREAK = 0
LAST_LOSS = 0
LAST_TRADE = None
BOT_RUNNING = False

# ====================================================
# 📱 FUNCIONES TELEGRAM
# ====================================================
def send(msg):
    if TOKEN and CHAT_ID:
        try:
            requests.post(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"},
                timeout=8
            )
        except Exception as e:
            logging.error(f"Telegram: {str(e)}")

def listen_commands():
    global BOT_RUNNING
    last_update_id = 0
    while True:
        try:
            res = requests.get(
                f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                params={"offset": last_update_id + 1, "timeout": 30},
                timeout=35
            )
            data = res.json()
            if not data.get("ok"):
                time.sleep(2)
                continue

            for update in data.get("result", []):
                last_update_id = update["update_id"]
                msg = update.get("message", {})
                text = msg.get("text", "").strip().lower()
                chat_id = str(msg.get("chat", {}).get("id", ""))

                if chat_id != str(CHAT_ID):
                    continue

                if text == "/start":
                    if not BOT_RUNNING:
                        BOT_RUNNING = True
                        send("✅ <b>BOT INICIADO</b>\nAnalizando 16 pares en vivo y buscando entradas...")
                    else:
                        send("ℹ️ El bot ya está activo.")
                elif text == "/stop":
                    if BOT_RUNNING:
                        BOT_RUNNING = False
                        send("🛑 <b>BOT DETENIDO</b>")
                    else:
                        send("ℹ️ El bot ya está detenido.")

        except Exception as e:
            logging.error(f"Comandos: {str(e)}")
            time.sleep(1)

# ====================================================
# 🔄 REINICIO DIARIO
# ====================================================
def reset_day():
    global DAILY_TRADES, CURRENT_DAY, LOSS_STREAK, LAST_TRADE
    today = datetime.now(timezone.utc).day
    if today != CURRENT_DAY:
        DAILY_TRADES = 0
        LOSS_STREAK = 0
        LAST_TRADE = None
        CURRENT_DAY = today
        if BOT_RUNNING:
            send("🔄 <b>NUEVO DÍA</b> | Contadores reiniciados.")

# ====================================================
# 🔌 CONEXIÓN IQ OPTION
# ====================================================
def connect():
    attempts = 0
    while attempts < MAX_RECONNECT_ATTEMPTS:
        try:
            if not EMAIL or not PASSWORD:
                send("❌ ERROR: Credenciales IQ Option no configuradas.")
                time.sleep(10)
                attempts += 1
                continue

            iq = IQ_Option(EMAIL, PASSWORD)
            ok, reason = iq.connect()
            if ok:
                iq.change_balance("PRACTICE")
                balance = iq.get_balance()
                send(f"✅ <b>CONECTADO EXITOSAMENTE</b>\nSaldo: ${balance:.2f}\nAnalizando {len(PAIRS)} activos.")
                return iq
            else:
                send(f"❌ Conexión fallida: {reason}")
        except Exception as e:
            send(f"❌ Error conexión: {str(e)}")
        attempts += 1
        time.sleep(RECONNECT_DELAY)
    send("💥 Reintentando conexión en 30 segundos...")
    time.sleep(30)
    return connect()

# ====================================================
# 📥 OBTENER DATOS
# ====================================================
def get_df(iq, pair):
    try:
        if not iq.check_connect():
            iq = connect()
            if not iq:
                return None

        data = iq.get_candles(pair, TIMEFRAME_M1, 40, time.time())
        if not data or len(data) < 25:
            return None

        df = pd.DataFrame(data)
        df.rename(columns={"max": "high", "min": "low"}, inplace=True)
        df[["open", "close", "high", "low", "volume"]] = df[["open", "close", "high", "low", "volume"]].astype(float)
        return df

    except Exception as e:
        logging.error(f"Datos {pair}: {str(e)}")
        return None

# ====================================================
# 🧠 BUCLE PRINCIPAL
# ====================================================
def main():
    global BOT_RUNNING, LOSS_STREAK, LAST_LOSS, DAILY_TRADES, LAST_TRADE
    threading.Thread(target=listen_commands, daemon=True).start()

    iq = connect()
    last_candle = None
    send("ℹ️ <b>SISTEMA LISTO</b>\nEnvía /start para iniciar análisis de todos los pares.")

    while True:
        try:
            if not BOT_RUNNING:
                time.sleep(2)
                continue

            reset_day()

            if not iq.check_connect():
                iq = connect()
                time.sleep(2)
                continue

            if DAILY_TRADES >= MAX_DAILY_TRADES:
                send("ℹ️ Límite diario de operaciones alcanzado.")
                BOT_RUNNING = False
                time.sleep(300)
                continue

            if LOSS_STREAK >= MAX_LOSS_STREAK:
                restante = int(PAUSE_TIME - (time.time() - LAST_LOSS))
                if restante > 0:
                    send(f"⏸️ Pausa de seguridad: {restante//60} minutos restantes.")
                    time.sleep(10)
                    continue
                else:
                    LOSS_STREAK = 0
                    LAST_TRADE = None
                    send("✅ Pausa finalizada. Buscando nuevas entradas...")

            server_time = iq.get_server_timestamp()
            sec = server_time % 60
            current_candle = int(server_time // 60)

            if current_candle == last_candle:
                time.sleep(0.05)
                continue
            last_candle = current_candle

            mejor_opcion = None
            mayor_fuerza = 0

            # Búsqueda en TODOS los pares
            if 25 <= sec <= 58:
                for pair in PAIRS:
                    df = get_df(iq, pair)
                    if df is None:
                        continue

                    resultado = get_trend_signal(df)
                    if resultado is not None:
                        signal, fuerza, direccion = resultado
                        if fuerza >= FUERZA_MINIMA and fuerza > mayor_fuerza:
                            mayor_fuerza = fuerza
                            mejor_opcion = (pair, signal, fuerza, direccion)

            if 56 <= sec <= 59.9 and mejor_opcion is not None:
                pair, signal, fuerza, direccion = mejor_opcion

                if (pair, signal) == LAST_TRADE:
                    continue
                LAST_TRADE = (pair, signal)

                send(f"""🎯 <b>ENTRADA DETECTADA</b>
💹 Activo: {pair}
📈 Tendencia: {direccion.upper()}
💪 Fuerza: {fuerza}/100
📊 Operación: {'🟢 COMPRA' if signal == 'call' else '🔴 VENTA'}
⏱️ Vencimiento: 1 minuto""")

                status, trade_id = iq.buy(BASE_AMOUNT, pair, signal, EXPIRATION)

                if status:
                    DAILY_TRADES += 1
                    send(f"🚀 <b>OPERACIÓN EJECUTADA</b>\nMonto: ${BASE_AMOUNT:.2f} | Total hoy: {DAILY_TRADES}/{MAX_DAILY_TRADES}")

                    time.sleep(65)
                    try:
                        res = iq.check_win_v4(trade_id)
                        if res is None:
                            send("⚠️ No se pudo verificar el resultado.")
                            continue

                        if res < 0:
                            LOSS_STREAK += 1
                            LAST_LOSS = time.time()
                            send(f"❌ <b>OPERACIÓN PERDIDA</b> | -${abs(res):.2f}\nRacha: {LOSS_STREAK}/{MAX_LOSS_STREAK}")
                        else:
                            LOSS_STREAK = 0
                            send(f"✅ <b>OPERACIÓN GANADA</b> | +${res:.2f}\n_________________________")

                    except Exception as e:
                        send(f"⚠️ Error al verificar: {str(e)}")
                else:
                    send(f"❌ No se pudo ejecutar la operación en {pair}")

            time.sleep(0.02)

        except Exception as e:
            send(f"💥 Error: {str(e)} | Reiniciando...")
            logging.exception("Error en bucle principal")
            time.sleep(3)
            try:
                iq = connect()
            except:
                pass

if __name__ == "__main__":
    required = ["IQ_EMAIL", "IQ_PASSWORD", "TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID"]
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        print(f"❌ Faltan variables de entorno: {', '.join(missing)}")
        sys.exit(1)
    main()

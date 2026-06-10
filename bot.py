import time
import os
import requests
import pandas as pd
import numpy as np
import sys
import logging
from datetime import datetime, UTC

from strategy import get_signal
from iqoptionapi.stable_api import IQ_Option

logging.basicConfig(
    level=logging.CRITICAL,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ==========================================
# CONFIGURACIÓN
# ==========================================
EMAIL = os.getenv("IQ_EMAIL")
PASSWORD = os.getenv("IQ_PASSWORD")
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

EXPIRATION = 1
BASE_AMOUNT = 10
TIMEFRAME_M1 = 60

PAIRS = [
    "EURUSD-OTC", "GBPUSD-OTC", "USDCHF-OTC",
    "EURGBP-OTC", "EURJPY-OTC", "GBPJPY-OTC"
]

MAX_DAILY_TRADES = 15
MAX_LOSS_STREAK = 2
PAUSE_TIME = 300
MIN_CONFIANZA = 75  # Solo alta probabilidad
MAX_RECONNECT_ATTEMPTS = 5
RECONNECT_DELAY = 5

DAILY_TRADES = 0
CURRENT_DAY = datetime.now(UTC).day
LOSS_STREAK = 0
LAST_LOSS = 0
LAST_PROCESSED_CANDLE = -1
PENDING_SIGNAL = None
LAST_NOTIFIED = None

# ====================================================
# MENSAJES
# ====================================================
def send(msg):
    if TOKEN and CHAT_ID:
        try:
            requests.post(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"},
                timeout=5
            )
        except:
            pass

def reset_day():
    global DAILY_TRADES, CURRENT_DAY, LOSS_STREAK, PENDING_SIGNAL, LAST_NOTIFIED
    today = datetime.now(UTC).day
    if today != CURRENT_DAY:
        DAILY_TRADES = 0
        LOSS_STREAK = 0
        PENDING_SIGNAL = None
        LAST_NOTIFIED = None
        CURRENT_DAY = today
        send("🔄 <b>NUEVO DÍA</b> | Entradas solo en soporte/resistencia")

def connect():
    attempts = 0
    while attempts < MAX_RECONNECT_ATTEMPTS:
        try:
            iq = IQ_Option(EMAIL, PASSWORD)
            status, reason = iq.connect()
            if status:
                balance = iq.get_balance()
                send(f"✅ CONECTADO | Saldo: ${balance:.2f} | Modo: Soporte/Resistencia")
                return iq
            attempts += 1
            time.sleep(RECONNECT_DELAY)
        except:
            attempts += 1
            time.sleep(RECONNECT_DELAY)
    send("❌ Conexión fallida")
    time.sleep(30)
    return connect()

def get_df(iq, pair, tf):
    try:
        if not iq.check_connect():
            iq = connect()
        data = iq.get_candles(pair, tf, 100, time.time())
        if not data or len(data) < 30:
            return None
        df = pd.DataFrame(data)
        df.rename(columns={"max": "high", "min": "low"}, inplace=True)
        df = df.astype({"open": float, "close": float, "high": float, "low": float, "volume": float})
        return df
    except:
        return None

# ====================================================
# BUCLE PRINCIPAL
# ====================================================
def main():
    global LOSS_STREAK, LAST_LOSS, DAILY_TRADES, LAST_PROCESSED_CANDLE, PENDING_SIGNAL, LAST_NOTIFIED
    iq = connect()

    while True:
        try:
            reset_day()
            if not iq.check_connect():
                iq = connect()
                time.sleep(2)
                continue

            if DAILY_TRADES >= MAX_DAILY_TRADES:
                time.sleep(120)
                continue
            if LOSS_STREAK >= MAX_LOSS_STREAK:
                remaining = int(PAUSE_TIME - (time.time() - LAST_LOSS))
                if remaining > 0:
                    time.sleep(10)
                    continue
                LOSS_STREAK = 0

            server_time = iq.get_server_timestamp()
            sec = server_time % 60
            current_candle = int(server_time // 60)

            # ANÁLISIS: segundos 25 a 57
            if 25 <= sec <= 57 and current_candle != LAST_PROCESSED_CANDLE:
                LAST_PROCESSED_CANDLE = current_candle
                best_pair = None
                best_signal = None
                best_conf = 0

                for pair in PAIRS:
                    df = get_df(iq, pair, TIMEFRAME_M1)
                    if df is None:
                        continue
                    s, conf = get_signal(df)
                    if s and conf >= MIN_CONFIANZA and conf > best_conf:
                        best_pair = pair
                        best_signal = s
                        best_conf = conf

                if best_pair:
                    PENDING_SIGNAL = (best_pair, best_signal)
                    if (best_pair, best_signal) != LAST_NOTIFIED:
                        send(f"🔍 CIERRE EN NIVEL CLAVE: {best_pair} | {best_signal.upper()} | Prob: {best_conf}%\n⏳ Ejecución en vela siguiente")
                        LAST_NOTIFIED = (best_pair, best_signal)
                else:
                    PENDING_SIGNAL = None
                    LAST_NOTIFIED = None

            # EJECUCIÓN EXACTA: 59.7 a 00.3
            if 59.7 <= sec <= 59.99 or 0 <= sec <= 0.3:
                if not PENDING_SIGNAL:
                    continue
                pair, direction = PENDING_SIGNAL
                PENDING_SIGNAL = None
                LAST_NOTIFIED = None

                status, trade_id = iq.buy(BASE_AMOUNT, pair, direction, EXPIRATION)
                if status:
                    DAILY_TRADES += 1
                    tipo = "🟢 COMPRA (CALL)" if direction == "call" else "🔴 VENTA (PUT)"
                    send(f"""🚀 OPERACIÓN EJECUTADA
📊 Activo: {pair}
📍 Entrada: Reversión en soporte/resistencia
⏱️ Expiración: 1 minuto
📌 Tipo: {tipo}
💲 Monto: ${BASE_AMOUNT}
🔄 #Op: {DAILY_TRADES}/{MAX_DAILY_TRADES}""")

                    time.sleep(65)
                    res = iq.check_win_v4(trade_id)
                    if res is None:
                        send("⚠️ Sin resultado")
                        continue
                    if res < 0:
                        LOSS_STREAK += 1
                        LAST_LOSS = time.time()
                        send(f"❌ LOSS | -${abs(res):.2f} | Rachas: {LOSS_STREAK}/{MAX_LOSS_STREAK}")
                    else:
                        LOSS_STREAK = 0
                        send(f"✅ WIN | +${res:.2f}\n_________________________")

            time.sleep(0.03)

        except Exception as e:
            send(f"💥 ERROR: {str(e)}")
            time.sleep(5)
            iq = connect()

if __name__ == "__main__":
    required = ["IQ_EMAIL", "IQ_PASSWORD", "TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID"]
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        print(f"Faltan variables: {missing}")
        sys.exit(1)
    main()

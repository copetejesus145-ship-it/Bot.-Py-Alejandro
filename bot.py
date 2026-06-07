import time
import os
import requests
import pandas as pd
import sys
import logging
from datetime import datetime, timezone

# Importación correcta
from strategy import get_trend_signal

from iqoptionapi.stable_api import IQ_Option

# Configuración de logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ==========================================
# ⚙️ CONFIGURACIÓN ULTRA EXIGENTE
# ==========================================
EMAIL = os.getenv("IQ_EMAIL")
PASSWORD = os.getenv("IQ_PASSWORD")
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

EXPIRATION = 1
BASE_AMOUNT = 25
TIMEFRAME_M1 = 60

# Activos más estables y con menor ruido
PAIRS = [
    "EURUSD-OTC", "GBPUSD-OTC", "EURGBP-OTC"
]

MAX_DAILY_TRADES = 4          # Máximo 4 operaciones por día
MAX_LOSS_STREAK = 1           # Se detiene después de 1 sola pérdida
PAUSE_TIME = 2400             # Pausa de 40 minutos tras pérdida
MAX_RECONNECT_ATTEMPTS = 5
RECONNECT_DELAY = 5
FUERZA_MINIMA = 75            # ✅ Solo señales de 75/100 en adelante

DAILY_TRADES = 0
CURRENT_DAY = datetime.now(timezone.utc).day
LOSS_STREAK = 0
LAST_LOSS = 0
LAST_TRADE = None

# ====================================================
# 📱 ENVÍO DE MENSAJES TELEGRAM
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
            logging.error(f"Error Telegram: {str(e)}")

# ====================================================
# ⏰ HORARIO DE OPERACIÓN SOLO DE ALTA LIQUIDEZ
# ====================================================
def es_hora_optima():
    hora_utc = datetime.now(timezone.utc).hour
    hora_bogota = hora_utc - 5
    # Solo opera en horario europeo y apertura de EE.UU: mayor volumen y tendencia clara
    return 4 <= hora_bogota <= 11

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
        send("🔄 <b>NUEVO DÍA INICIADO</b> | Buscando señales de MÁXIMA PRECISIÓN.")

# ====================================================
# 🔌 CONEXIÓN IQ OPTION
# ====================================================
def connect():
    attempts = 0
    while attempts < MAX_RECONNECT_ATTEMPTS:
        try:
            if not EMAIL or not PASSWORD:
                send("❌ ERROR: Credenciales IQ no configuradas")
                time.sleep(10)
                attempts += 1
                continue

            iq = IQ_Option(EMAIL, PASSWORD)
            status, reason = iq.connect()

            if status:
                iq.change_balance("PRACTICE")
                balance = iq.get_balance()
                send(f"✅ <b>CONECTADO</b> | Saldo: ${balance:.2f}")
                return iq
            else:
                send(f"❌ Error conexión: {reason} | Intento {attempts+1}")

        except Exception as e:
            send(f"❌ Error: {str(e)} | Intento {attempts+1}")

        attempts += 1
        time.sleep(RECONNECT_DELAY)

    send("💥 Sin conexión. Reintentando en 30s...")
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

        data = iq.get_candles(pair, TIMEFRAME_M1, 60, time.time())
        if not data or len(data) < 30:
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
    global LOSS_STREAK, LAST_LOSS, DAILY_TRADES, LAST_TRADE
    iq = connect()
    last_candle = None

    while True:
        try:
            reset_day()

            if not es_hora_optima():
                time.sleep(60)
                continue

            if not iq.check_connect():
                iq = connect()
                time.sleep(2)
                continue

            if DAILY_TRADES >= MAX_DAILY_TRADES:
                send("ℹ️ Límite diario de operaciones alcanzado.")
                time.sleep(300)
                continue

            if LOSS_STREAK >= MAX_LOSS_STREAK:
                remaining = int(PAUSE_TIME - (time.time() - LAST_LOSS))
                if remaining > 0:
                    send(f"⏸️ Pausa de seguridad activa: {remaining//60} minutos restantes.")
                    time.sleep(60)
                    continue
                else:
                    LOSS_STREAK = 0
                    LAST_TRADE = None
                    send("✅ Pausa finalizada. Buscando señales premium...")

            server_time = iq.get_server_timestamp()
            sec = server_time % 60
            current_candle = int(server_time // 60)

            if current_candle == last_candle:
                time.sleep(0.1)
                continue
            last_candle = current_candle

            mejor_opcion = None
            mayor_fuerza = 0

            if 40 <= sec <= 55:
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

            if 57 <= sec <= 59.9 and mejor_opcion is not None:
                pair, signal, fuerza, direccion = mejor_opcion

                if (pair, signal) == LAST_TRADE:
                    continue
                LAST_TRADE = (pair, signal)

                send(f"""🎯 <b>SEÑAL PREMIUM</b>
💹 Activo: {pair}
📈 Tendencia: {direccion.upper()}
💪 Fuerza: {fuerza}/100
📊 Señal: {'🟢 COMPRA' if signal == 'call' else '🔴 VENTA'}
⚡ Ejecutando...""")

                status, trade_id = iq.buy(BASE_AMOUNT, pair, signal, EXPIRATION)

                if status:
                    DAILY_TRADES += 1
                    send(f"""🚀 <b>OPERACIÓN EJECUTADA</b>
💲 Monto: ${BASE_AMOUNT:.2f}
🔄 {DAILY_TRADES}/{MAX_DAILY_TRADES}""")

                    time.sleep(65)
                    try:
                        res = iq.check_win_v4(trade_id)
                        if res is None:
                            send("⚠️ Sin resultado disponible")
                            continue

                        if res < 0:
                            LOSS_STREAK += 1
                            LAST_LOSS = time.time()
                            send(f"❌ <b>PÉRDIDA</b> | -${abs(res):.2f}\n⚠️ Activando pausa de seguridad.")
                        else:
                            LOSS_STREAK = 0
                            send(f"✅ <b>GANANCIA</b> | +${res:.2f}\n_________________________")

                    except Exception as e:
                        send(f"⚠️ Error al verificar: {str(e)}")
                else:
                    send(f"❌ No se pudo ejecutar en {pair}")

            time.sleep(0.05)

        except Exception as e:
            send(f"💥 ERROR: {str(e)} | Reiniciando...")
            logging.exception("Error en bucle principal")
            time.sleep(5)
            try:
                iq = connect()
            except:
                pass

if __name__ == "__main__":
    required_vars = ["IQ_EMAIL", "IQ_PASSWORD", "TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID"]
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        print(f"❌ Faltan variables: {', '.join(missing)}")
        sys.exit(1)
    main()

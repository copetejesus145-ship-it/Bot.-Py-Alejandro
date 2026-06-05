import time
import os
import requests
import pandas as pd
import sys
import logging
from datetime import datetime, UTC  # ✅ Importamos UTC correctamente

# ✅ Importamos la estrategia
from strategy import get_signal

from iqoptionapi.stable_api import IQ_Option

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ==========================================
# 🔑 CONFIGURACIÓN GENERAL
# ==========================================
EMAIL = os.getenv("IQ_EMAIL")
PASSWORD = os.getenv("IQ_PASSWORD")
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ⚙️ PARÁMETROS DE OPERACIÓN
EXPIRATION = 1                  # ⏱️ Vencimiento: 1 minuto
BASE_AMOUNT = 25                # 💰 Monto por operación
TIMEFRAME_M1 = 60               # 🕯️ Velas de 1 minuto

# 🎯 Activos OTC
PAIRS = [
    "EURUSD-OTC", "GBPUSD-OTC", "USDCHF-OTC", 
    "EURGBP-OTC", "EURJPY-OTC", "GBPJPY-OTC"
]

# 🛑 GESTIÓN DE RIESGO
MAX_DAILY_TRADES = 15           # Máx operaciones por día
MAX_LOSS_STREAK = 2             # Detener tras 2 pérdidas seguidas
PAUSE_TIME = 600                # Pausa 10 minutos tras pérdidas
MAX_RECONNECT_ATTEMPTS = 5
RECONNECT_DELAY = 5

# 🚦 Variables globales
DAILY_TRADES = 0
CURRENT_DAY = datetime.now(UTC).day  # ✅ Corregido
LOSS_STREAK = 0
LAST_LOSS = 0
LAST_SIGNAL = None

# ====================================================
#   📱 ENVÍO DE MENSAJES A TELEGRAM
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
#   🔄 REINICIO DE CONTADORES DIARIOS
# ====================================================
def reset_day():
    global DAILY_TRADES, CURRENT_DAY, LOSS_STREAK, LAST_SIGNAL
    today = datetime.now(UTC).day  # ✅ Corregido: usa zona horaria UTC
    if today != CURRENT_DAY:
        DAILY_TRADES = 0
        LOSS_STREAK = 0
        LAST_SIGNAL = None
        CURRENT_DAY = today
        send("🔄 <b>NUEVO DÍA</b> | Contadores reiniciados.")

# ====================================================
#   🔌 CONEXIÓN A IQ OPTION
# ====================================================
def connect():
    attempts = 0
    while attempts < MAX_RECONNECT_ATTEMPTS:
        try:
            if not EMAIL or not PASSWORD:
                send("❌ ERROR: Credenciales IQ_EMAIL o IQ_PASSWORD no configuradas")
                time.sleep(10)
                attempts += 1
                continue

            iq = IQ_Option(EMAIL, PASSWORD)
            status, reason = iq.connect()

            if status:
                iq.change_balance("PRACTICE")  # Cambia a "REAL" cuando estés listo
                balance = iq.get_balance()
                send(f"✅ <b>CONECTADO</b> | Saldo: ${balance:.2f}")
                return iq
            else:
                send(f"❌ Conexión fallida: {reason} | Intento {attempts+1}/{MAX_RECONNECT_ATTEMPTS}")

        except Exception as e:
            send(f"❌ Error de conexión: {str(e)} | Intento {attempts+1}/{MAX_RECONNECT_ATTEMPTS}")

        attempts += 1
        time.sleep(RECONNECT_DELAY)

    send("💥 No se pudo conectar. Reintentando en 30s...")
    time.sleep(30)
    return connect()

# ====================================================
#   📥 OBTENER Y VALIDAR DATOS DE MERCADO
# ====================================================
def get_df(iq, pair, tf):
    try:
        if not iq.check_connect():
            send("⚠️ Conexión perdida, reconectando...")
            iq = connect()
            if not iq:
                return None

        data = iq.get_candles(pair, tf, 40, time.time())

        if not data or len(data) < 15:
            logging.warning(f"Datos insuficientes para {pair}")
            return None

        df = pd.DataFrame(data)
        required_cols = ["open", "close", "max", "min", "volume"]
        if not all(col in df.columns for col in required_cols):
            return None

        df.rename(columns={"max": "high", "min": "low"}, inplace=True)
        df[["open", "close", "high", "low", "volume"]] = df[["open", "close", "high", "low", "volume"]].astype(float)

        return df

    except Exception as e:
        logging.error(f"Error en datos {pair}: {str(e)}")
        return None

# ====================================================
#   🧠 BUCLE PRINCIPAL
# ====================================================
def main():
    global LOSS_STREAK, LAST_LOSS, DAILY_TRADES, LAST_SIGNAL
    iq = connect()
    last_candle = None

    while True:
        try:
            reset_day()

            if not iq.check_connect():
                iq = connect()
                time.sleep(2)
                continue

            # ======================================
            # 🛑 CONTROLES DE SEGURIDAD
            # ======================================
            if DAILY_TRADES >= MAX_DAILY_TRADES:
                time.sleep(60)
                continue

            if LOSS_STREAK >= MAX_LOSS_STREAK:
                remaining = int(PAUSE_TIME - (time.time() - LAST_LOSS))
                if remaining > 0:
                    time.sleep(10)
                    continue
                else:
                    LOSS_STREAK = 0
                    LAST_SIGNAL = None
                    send("✅ Pausa finalizada. Reanudando.")

            # ======================================
            # ⏱️ TIEMPO PRECISO DEL SERVIDOR
            # ======================================
            server_time = iq.get_server_timestamp()
            sec = server_time % 60
            current_candle = int(server_time // 60)

            if current_candle == last_candle:
                time.sleep(0.1)
                continue

            # ======================================
            # 🔍 ANÁLISIS (segundos 40 a 58)
            # ======================================
            best_pair = None
            best_signal = None

            if 40 <= sec <= 58:
                for pair in PAIRS:
                    df = get_df(iq, pair, TIMEFRAME_M1)
                    if df is None or len(df) < 15:
                        continue

                    try:
                        signal = get_signal(df)
                    except Exception as e:
                        send(f"⚠️ Error estrategia {pair}: {str(e)}")
                        continue

                    if signal in ["call", "put"]:
                        if (pair, signal) != LAST_SIGNAL:
                            best_pair = pair
                            best_signal = signal
                            LAST_SIGNAL = (best_pair, best_signal)
                            send(f"🔍 Señal detectada: {pair} | {best_signal.upper()}")
                            break

            # ======================================
            # ⚡ EJECUCIÓN (cierre exacto de vela)
            # ======================================
            if 59.2 <= sec <= 59.98:
                if not best_pair or not best_signal:
                    time.sleep(0.1)
                    continue

                last_candle = current_candle

                status, trade_id = iq.buy(BASE_AMOUNT, best_pair, best_signal, EXPIRATION)

                if status:
                    DAILY_TRADES += 1
                    tipo = "🟢 <b>COMPRA (CALL)</b>" if best_signal == "call" else "🔴 <b>VENTA (PUT)</b>"
                    send(f"""🚀 <b>OPERACIÓN EJECUTADA</b>
💹 Activo: {best_pair}
📈 Tipo: {tipo}
💲 Monto: ${BASE_AMOUNT:.2f}
🔄 #Op: {DAILY_TRADES}/{MAX_DAILY_TRADES}""")

                    time.sleep(65)
                    try:
                        res = iq.check_win_v4(trade_id)
                        if res is None:
                            send("⚠️ No se pudo obtener resultado")
                            continue

                        if res < 0:
                            LOSS_STREAK += 1
                            LAST_LOSS = time.time()
                            send(f"❌ <b>LOSS</b> | -${abs(res):.2f}\n⚠️ Rachas: {LOSS_STREAK}/{MAX_LOSS_STREAK}")
                        else:
                            LOSS_STREAK = 0
                            send(f"✅ <b>WIN</b> | +${res:.2f}\n_________________________")

                    except Exception as e:
                        send(f"⚠️ Error al verificar: {str(e)}")
                else:
                    send(f"❌ No se pudo ejecutar operación")

            time.sleep(0.05)

        except Exception as e:
            send(f"💥 ERROR: {str(e)} | Reconectando...")
            logging.exception("Error en bucle")
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

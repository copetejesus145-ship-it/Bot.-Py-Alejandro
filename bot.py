import time
import os
import requests
import pandas as pd
import sys
import logging
from datetime import datetime, UTC

# Importar estrategia
from strategy import get_signal

from iqoptionapi.stable_api import IQ_Option

# Configuración de logs
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

# 🎯 Activos OTC a monitorear
PAIRS = [
    "EURUSD-OTC", "GBPUSD-OTC", "USDCHF-OTC",
    "EURGBP-OTC", "EURJPY-OTC", "GBPJPY-OTC"
]

# 🛑 GESTIÓN DE RIESGO
MAX_DAILY_TRADES = 10           # Máximo 10 operaciones por día
MAX_LOSS_STREAK = 2             # Detener tras 2 pérdidas seguidas
PAUSE_TIME = 1200               # Pausa 20 minutos tras pérdidas
MAX_RECONNECT_ATTEMPTS = 5
RECONNECT_DELAY = 5

# 🚦 Variables de control
DAILY_TRADES = 0
CURRENT_DAY = datetime.now(UTC).day
LOSS_STREAK = 0
LAST_LOSS = 0
LAST_SIGNAL = None
MEJOR_PAR = None
MEJOR_FUERZA = 0

# ====================================================
# 📱 ENVÍO DE MENSAJES A TELEGRAM
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
# 🔄 REINICIO DE CONTADORES DIARIOS
# ====================================================
def reset_day():
    global DAILY_TRADES, CURRENT_DAY, LOSS_STREAK, LAST_SIGNAL, MEJOR_PAR, MEJOR_FUERZA
    today = datetime.now(UTC).day
    if today != CURRENT_DAY:
        DAILY_TRADES = 0
        LOSS_STREAK = 0
        LAST_SIGNAL = None
        MEJOR_PAR = None
        MEJOR_FUERZA = 0
        CURRENT_DAY = today
        send("🔄 <b>NUEVO DÍA INICIADO</b> | Buscando la mejor continuidad.")

# ====================================================
# 🔌 CONEXIÓN A IQ OPTION
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
                iq.change_balance("PRACTICE")  # Cambiar a "REAL" cuando estés listo
                balance = iq.get_balance()
                send(f"✅ <b>BOT CONECTADO</b> | Saldo: ${balance:.2f}")
                return iq
            else:
                send(f"❌ Error de conexión: {reason} | Intento {attempts+1}/{MAX_RECONNECT_ATTEMPTS}")

        except Exception as e:
            send(f"❌ Error de conexión: {str(e)} | Intento {attempts+1}/{MAX_RECONNECT_ATTEMPTS}")

        attempts += 1
        time.sleep(RECONNECT_DELAY)

    send("💥 No se pudo conectar. Reintentando en 30s...")
    time.sleep(30)
    return connect()

# ====================================================
# 📥 OBTENER DATOS DE MERCADO
# ====================================================
def get_df(iq, pair, tf):
    try:
        if not iq.check_connect():
            send("⚠️ Conexión perdida, reconectando...")
            iq = connect()
            if not iq:
                return None

        data = iq.get_candles(pair, tf, 60, time.time())

        if not data or len(data) < 20:
            return None

        df = pd.DataFrame(data)
        required_cols = ["open", "close", "max", "min", "volume"]
        if not all(col in df.columns for col in required_cols):
            return None

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
    global LOSS_STREAK, LAST_LOSS, DAILY_TRADES, LAST_SIGNAL, MEJOR_PAR, MEJOR_FUERZA
    iq = connect()
    last_candle = None
    senal_pendiente = None

    while True:
        try:
            reset_day()

            if not iq.check_connect():
                iq = connect()
                time.sleep(2)
                continue

            # 🛑 CONTROLES DE SEGURIDAD
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
                    senal_pendiente = None
                    send("✅ Pausa finalizada. Buscando nuevas oportunidades...")

            # ⏱️ TIEMPO PRECISO DEL SERVIDOR
            server_time = iq.get_server_timestamp()
            sec = server_time % 60
            current_candle = int(server_time // 60)

            if current_candle == last_candle:
                time.sleep(0.1)
                continue

            last_candle = current_candle

            # 🔍 PASO 1: ANALIZAR TODOS LOS PARES Y ELEGIR EL MEJOR
            mejor_opcion = None
            mayor_fuerza = 0

            if 40 <= sec <= 55:
                for pair in PAIRS:
                    df = get_df(iq, pair, TIMEFRAME_M1)
                    if df is None:
                        continue

                    try:
                        resultado = get_signal(df)
                        if resultado is not None:
                            signal, fuerza = resultado
                            if fuerza > mayor_fuerza:
                                mayor_fuerza = fuerza
                                mejor_opcion = (pair, signal, fuerza)
                    except Exception as e:
                        continue

                # Guardar la mejor opción para ejecutarla en la siguiente vela
                if mejor_opcion and mayor_fuerza >= 60:  # Solo fuerza mínima aceptable
                    pair, signal, fuerza = mejor_opcion
                    if (pair, signal) != LAST_SIGNAL:
                        senal_pendiente = mejor_opcion
                        LAST_SIGNAL = (pair, signal)
                        send(f"""🎯 <b>CONTINUIDAD DETECTADA - SE EJECUTARÁ EN SIGUIENTE VELA</b>
💹 Activo: {pair}
📊 Dirección: {'🟢 ALCISTA FUERTE' if signal == 'call' else '🔴 BAJISTA FUERTE'}
💪 Fuerza: {fuerza}/100""")

            # ⚡ PASO 2: EJECUTAR LA SEÑAL PENDIENTE AL CIERRE DE VELA
            if 57 <= sec <= 59.98 and senal_pendiente is not None:
                pair, signal, fuerza = senal_pendiente

                status, trade_id = iq.buy(BASE_AMOUNT, pair, signal, EXPIRATION)

                if status:
                    DAILY_TRADES += 1
                    tipo = "🟢 <b>COMPRA - CONTINUIDAD FUERTE</b>" if signal == "call" else "🔴 <b>VENTA - CONTINUIDAD FUERTE</b>"
                    send(f"""🚀 <b>OPERACIÓN EJECUTADA</b>
💹 Activo: {pair}
📈 Tipo: {tipo}
💲 Monto: ${BASE_AMOUNT:.2f}
🔄 #Op: {DAILY_TRADES}/{MAX_DAILY_TRADES}""")

                    senal_pendiente = None
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
                    send(f"❌ No se pudo ejecutar operación en {pair}")
                    senal_pendiente = None

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

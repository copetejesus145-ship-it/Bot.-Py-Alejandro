import time
import os
import requests
import pandas as pd
import sys
import logging
from datetime import datetime, UTC

# ✅ Importamos la estrategia de estructura
from strategy import get_signal

from iqoptionapi.stable_api import IQ_Option

# Configuración de logging
logging.basicConfig(
    level=logging.CRITICAL,
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
EXPIRATION = 1                  # ⏱️ EXPIRACIÓN: 1 MINUTO
BASE_AMOUNT = 10                # 💰 MONTO POR OPERACIÓN (coincide con tu mensaje)
TIMEFRAME_M1 = 60               # 🕯️ VELAS DE 1 MINUTO

# 🎯 ACTIVOS OTC
PAIRS = [
    "EURUSD-OTC", "GBPUSD-OTC", "USDCHF-OTC", 
    "EURGBP-OTC", "EURJPY-OTC", "GBPJPY-OTC"
]

# 🛑 GESTIÓN DE RIESGO
MAX_DAILY_TRADES = 20           # Máx operaciones por día
MAX_LOSS_STREAK = 2             # Detener si pierdes 2 seguidas
PAUSE_TIME = 300                # Pausa 5 min tras pérdida
MAX_RECONNECT_ATTEMPTS = 5      # Intentos máximos de reconexión
RECONNECT_DELAY = 5             # Tiempo entre intentos

# 🚦 VARIABLES GLOBALES
DAILY_TRADES = 0
CURRENT_DAY = datetime.now(UTC).day
LOSS_STREAK = 0
LAST_LOSS = 0
LAST_PROCESSED_CANDLE = -1     # Última vela ya analizada
PENDING_SIGNAL = None          # Señal guardada para ejecutar en la vela siguiente
LAST_NOTIFIED = None           # Evita mensajes repetidos

# ====================================================
#   📱 ENVÍO DE MENSAJES A TELEGRAM
# ====================================================
def send(msg):
    if TOKEN and CHAT_ID:
        try:
            requests.post(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"},
                timeout=5
            )
        except Exception as e:
            logging.error(f"Error al enviar mensaje Telegram: {str(e)}")

# ====================================================
#   🔄 REINICIO DE CONTADORES CADA DÍA
# ====================================================
def reset_day():
    global DAILY_TRADES, CURRENT_DAY, LOSS_STREAK, PENDING_SIGNAL, LAST_NOTIFIED
    today = datetime.now(UTC).day
    if today != CURRENT_DAY:
        DAILY_TRADES = 0
        LOSS_STREAK = 0
        PENDING_SIGNAL = None
        LAST_NOTIFIED = None
        CURRENT_DAY = today
        send("🔄 <b>NUEVO DÍA INICIADO</b> | Contadores reiniciados.")

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
                balance_status = iq.change_balance("PRACTICE")
                if not balance_status:
                    send("⚠️ No se pudo cambiar a cuenta PRACTICE, usando cuenta actual")
                
                send("✅ <b>BOT CONECTADO</b> | Análisis por estructura - Ejecución en vela siguiente")
                return iq
            else:
                send(f"❌ Error de conexión: {reason} | Intento {attempts+1}/{MAX_RECONNECT_ATTEMPTS}")
        
        except Exception as e:
            send(f"❌ Error de conexión: {str(e)} | Intento {attempts+1}/{MAX_RECONNECT_ATTEMPTS}")
        
        attempts += 1
        time.sleep(RECONNECT_DELAY)
    
    send("💥 No se pudo conectar. Reintentando en 30 segundos...")
    time.sleep(30)
    return connect()

# ====================================================
#   📥 OBTENER DATOS DE MERCADO
# ====================================================
def get_df(iq, pair, tf):
    try:
        if not iq.check_connect():
            send("⚠️ Conexión perdida, reconectando...")
            iq = connect()
            if not iq:
                return None

        data = iq.get_candles(pair, tf, 80, time.time())
        
        if not data or len(data) < 20:
            return None
        
        df = pd.DataFrame(data)
        
        required_cols = ["open", "close", "max", "min", "volume"]
        if not all(col in df.columns for col in required_cols):
            return None
        
        df.rename(columns={"max": "high", "min": "low"}, inplace=True)
        df = df.astype({"open": float, "close": float, "high": float, "low": float, "volume": float})
        
        return df

    except Exception as e:
        logging.error(f"Error al obtener datos de {pair}: {str(e)}")
        return None

# ====================================================
#   🧠 LÓGICA PRINCIPAL: DETECTAR → GUARDAR → EJECUTAR EN SIGUIENTE VELA
# ====================================================
def main():
    global LOSS_STREAK, LAST_LOSS, DAILY_TRADES, LAST_PROCESSED_CANDLE, PENDING_SIGNAL, LAST_NOTIFIED
    iq = connect()

    while True:
        try:
            reset_day()

            if not iq.check_connect():
                send("🔌 Conexión perdida, reconectando...")
                iq = connect()
                time.sleep(2)
                continue

            # ======================================
            # 🛑 CONTROLES DE SEGURIDAD
            # ======================================
            if DAILY_TRADES >= MAX_DAILY_TRADES:
                time.sleep(30)
                continue

            if LOSS_STREAK >= MAX_LOSS_STREAK:
                remaining = int(PAUSE_TIME - (time.time() - LAST_LOSS))
                if remaining > 0:
                    time.sleep(10)
                    continue
                else:
                    LOSS_STREAK = 0

            # ======================================
            # ⏱️ TIEMPO DEL SERVIDOR
            # ======================================
            server_time = iq.get_server_timestamp()
            sec = server_time % 60
            current_candle = int(server_time // 60)  # Vela actual

            # ======================================
            # 🔍 FASE 1: ANALIZAR Y GUARDAR SEÑAL (Segundos 30 a 58)
            # ======================================
            if 30 <= sec <= 58 and current_candle != LAST_PROCESSED_CANDLE:
                LAST_PROCESSED_CANDLE = current_candle
                best_pair = None
                best_signal = None

                for pair in PAIRS:
                    df = get_df(iq, pair, TIMEFRAME_M1)
                    if df is None:
                        continue

                    try:
                        s = get_signal(df)
                    except Exception as e:
                        continue

                    if s in ["call", "put"]:
                        best_pair = pair
                        best_signal = s
                        break

                if best_pair and best_signal:
                    PENDING_SIGNAL = (best_pair, best_signal)
                    # Solo notificar una vez
                    if (best_pair, best_signal) != LAST_NOTIFIED:
                        send(f"🔍 Estructura detectada: {best_pair} | {best_signal.upper()}\n⏳ Se ejecutará en la vela siguiente")
                        LAST_NOTIFIED = (best_pair, best_signal)
                else:
                    PENDING_SIGNAL = None
                    LAST_NOTIFIED = None

            # ======================================
            # ⚡ FASE 2: EJECUTAR LA SEÑAL GUARDADA EN LA VELA SIGUIENTE
            # ======================================
            if 59.7 <= sec <= 59.99 or 0 <= sec <= 0.3:
                if not PENDING_SIGNAL:
                    continue

                # Extraemos la señal guardada y la limpiamos
                pair, direction = PENDING_SIGNAL
                PENDING_SIGNAL = None
                LAST_NOTIFIED = None

                # ✅ EJECUTAR ORDEN
                status, trade_id = iq.buy(BASE_AMOUNT, pair, direction, EXPIRATION)

                if status:
                    DAILY_TRADES += 1
                    tipo_op = "🟢 <b>COMPRA (CALL)</b>" if direction == "call" else "🔴 <b>VENTA (PUT)</b>"
                    send(f"""🚀 <b>OPERACIÓN EJECUTADA</b>
💹 Activo: {pair}
📍 Entrada: Inicio de vela siguiente
📊 Análisis: Estructura detectada previamente
📌 Tipo: {tipo_op}
💲 Monto: ${BASE_AMOUNT:.2f}
🔄 #Op: {DAILY_TRADES}/{MAX_DAILY_TRADES}""")

                    # ⏳ ESPERAR RESULTADO
                    time.sleep(65)
                    try:
                        resultado = iq.check_win_v4(trade_id)
                        if resultado is None:
                            send("⚠️ No se pudo verificar el resultado")
                            continue

                        if resultado < 0:
                            LOSS_STREAK += 1
                            LAST_LOSS = time.time()
                            send(f"❌ <b>LOSS</b> | Pérdida: ${abs(resultado):.2f}\n⚠️ Rachas: {LOSS_STREAK}/{MAX_LOSS_STREAK}")
                        else:
                            LOSS_STREAK = 0
                            send(f"✅ <b>WIN</b> | Ganancia: +${resultado:.2f}\n_________________________")
                    
                    except Exception as e:
                        send(f"⚠️ Error al obtener resultado: {str(e)}")
                else:
                    send(f"❌ No se pudo ejecutar orden en {pair}")

            time.sleep(0.05)

        except Exception as e:
            send(f"💥 <b>ERROR CRÍTICO:</b> {str(e)} | Reconectando...")
            time.sleep(5)
            try:
                iq = connect()
            except:
                pass

if __name__ == "__main__":
    required_vars = ["IQ_EMAIL", "IQ_PASSWORD", "TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID"]
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        print(f"❌ Faltan variables de entorno: {', '.join(missing)}")
        send(f"❌ Faltan configuraciones: {', '.join(missing)}")
        sys.exit(1)
    
    main()

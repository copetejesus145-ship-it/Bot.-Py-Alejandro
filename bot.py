import time
import os
import requests
import pandas as pd
import numpy as np
import sys
import logging
from datetime import datetime, UTC

# ✅ Importamos la estrategia ajustada
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
BASE_AMOUNT = 10                # 💰 MONTO POR OPERACIÓN
TIMEFRAME_M1 = 60               # 🕯️ VELAS DE 1 MINUTO

# 🎯 ACTIVOS OTC
PAIRS = [
    "EURUSD-OTC", "GBPUSD-OTC", "USDCHF-OTC", 
    "EURGBP-OTC", "EURJPY-OTC", "GBPJPY-OTC"
]

# 🛑 GESTIÓN DE RIESGO (ajustada para más operaciones)
MAX_DAILY_TRADES = 20           # Aumentamos límite diario
MAX_LOSS_STREAK = 3             # Permitimos hasta 3 pérdidas seguidas
PAUSE_TIME = 240                # Pausa 4 minutos tras pérdida
MIN_CONFIANZA = 60              # Bajamos el requisito mínimo de confianza
MAX_RECONNECT_ATTEMPTS = 5
RECONNECT_DELAY = 5

# 🚦 VARIABLES GLOBALES
DAILY_TRADES = 0
CURRENT_DAY = datetime.now(UTC).day
LOSS_STREAK = 0
LAST_LOSS = 0
LAST_PROCESSED_CANDLE = -1
PENDING_SIGNAL = None
LAST_NOTIFIED = None

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
#   🔄 REINICIO DE CONTADORES
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
        send("🔄 <b>NUEVO DÍA INICIADO</b> | Buscando oportunidades válidas.")

# ====================================================
#   🔌 CONEXIÓN A IQ OPTION
# ====================================================
def connect():
    attempts = 0
    while attempts < MAX_RECONNECT_ATTEMPTS:
        try:
            if not EMAIL or not PASSWORD:
                send("❌ ERROR: Credenciales no configuradas")
                time.sleep(10)
                attempts += 1
                continue

            iq = IQ_Option(EMAIL, PASSWORD)
            status, reason = iq.connect()
            
            if status:
                balance_status = iq.change_balance("PRACTICE")
                if not balance_status:
                    send("⚠️ No se pudo cambiar a cuenta PRACTICE, usando cuenta actual")
                
                balance = iq.get_balance()
                send(f"✅ <b>BOT CONECTADO</b> | Saldo: ${balance:.2f} | Modo: Equilibrado | Expiración: 1 min")
                return iq
            else:
                send(f"❌ Error conexión: {reason} | Intento {attempts+1}/{MAX_RECONNECT_ATTEMPTS}")
        
        except Exception as e:
            send(f"❌ Error conexión: {str(e)} | Intento {attempts+1}/{MAX_RECONNECT_ATTEMPTS}")
        
        attempts += 1
        time.sleep(RECONNECT_DELAY)
    
    send("💥 Conexión fallida. Reintentando en 30s...")
    time.sleep(30)
    return connect()

# ====================================================
#   📥 OBTENER Y VALIDAR DATOS
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
        logging.error(f"Datos error {pair}: {str(e)}")
        return None

# ====================================================
#   🧠 BUCLE PRINCIPAL
# ====================================================
def main():
    global LOSS_STREAK, LAST_LOSS, DAILY_TRADES, LAST_PROCESSED_CANDLE, PENDING_SIGNAL, LAST_NOTIFIED
    iq = connect()

    while True:
        try:
            reset_day()

            if not iq.check_connect():
                send("🔌 Reconectando...")
                iq = connect()
                time.sleep(2)
                continue

            # ======================================
            # 🛑 CONTROLES DE SEGURIDAD
            # ======================================
            if DAILY_TRADES >= MAX_DAILY_TRADES:
                send(f"ℹ️ Límite diario alcanzado ({MAX_DAILY_TRADES} operaciones). Esperando siguiente día.")
                time.sleep(120)
                continue

            if LOSS_STREAK >= MAX_LOSS_STREAK:
                remaining = int(PAUSE_TIME - (time.time() - LAST_LOSS))
                if remaining > 0:
                    send(f"⏸️ Pausa de seguridad activa: {remaining}s restantes")
                    time.sleep(10)
                    continue
                else:
                    LOSS_STREAK = 0
                    send("✅ Pausa finalizada. Reanudando búsqueda de señales.")

            # ======================================
            # ⏱️ TIEMPO DEL SERVIDOR
            # ======================================
            server_time = iq.get_server_timestamp()
            sec = server_time % 60
            current_candle = int(server_time // 60)

            # ======================================
            # 🔍 ANÁLISIS (Segundos 25 a 57)
            # ======================================
            if 25 <= sec <= 57 and current_candle != LAST_PROCESSED_CANDLE:
                LAST_PROCESSED_CANDLE = current_candle
                best_pair = None
                best_signal = None
                best_confianza = 0

                for pair in PAIRS:
                    df = get_df(iq, pair, TIMEFRAME_M1)
                    if df is None:
                        continue

                    try:
                        s, confianza = get_signal(df)
                    except Exception as e:
                        continue

                    # Aceptamos señales con confianza desde 60%
                    if s in ["call", "put"] and confianza >= MIN_CONFIANZA:
                        if confianza > best_confianza:
                            best_pair = pair
                            best_signal = s
                            best_confianza = confianza

                if best_pair and best_signal:
                    PENDING_SIGNAL = (best_pair, best_signal)
                    if (best_pair, best_signal) != LAST_NOTIFIED:
                        send(f"""🔍 SEÑAL DETECTADA
📊 Activo: {best_pair}
📈 Dirección: {best_signal.upper()}
✅ Confianza: {best_confianza}%
⏳ Entrada: Inicio de vela siguiente""")
                        LAST_NOTIFIED = (best_pair, best_signal)
                else:
                    PENDING_SIGNAL = None
                    LAST_NOTIFIED = None

            # ======================================
            # ⚡ EJECUCIÓN EXACTA
            # ======================================
            if 59.6 <= sec <= 59.99 or 0 <= sec <= 0.4:
                if not PENDING_SIGNAL:
                    continue

                pair, direction = PENDING_SIGNAL
                PENDING_SIGNAL = None
                LAST_NOTIFIED = None

                status, trade_id = iq.buy(BASE_AMOUNT, pair, direction, EXPIRATION)

                if status:
                    DAILY_TRADES += 1
                    tipo_op = "🟢 <b>COMPRA (CALL)</b>" if direction == "call" else "🔴 <b>VENTA (PUT)</b>"
                    send(f"""🚀 <b>OPERACIÓN EJECUTADA</b>
💹 Activo: {pair}
📍 Entrada: Inicio exacto de vela
⏱️ Expiración: 1 minuto
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
                        send(f"⚠️ Error al verificar resultado: {str(e)}")
                else:
                    send(f"❌ No se pudo ejecutar orden en {pair}")

            time.sleep(0.03)

        except Exception as e:
            send(f"💥 <b>ERROR CRÍTICO:</b> {str(e)} | Reiniciando...")
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
        send(f"❌ Faltan configuraciones: {', '.join(missing)}")
        sys.exit(1)
    
    main()

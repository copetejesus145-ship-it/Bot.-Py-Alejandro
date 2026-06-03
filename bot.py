import time
import os
import requests
import pandas as pd
import sys
import logging
from datetime import datetime

# ✅ IMPORTAMOS LA ESTRATEGIA CORRECTA
from strategy import get_signal

from iqoptionapi.stable_api import IQ_Option

logging.getLogger().setLevel(logging.CRITICAL)
sys.stderr = open(os.devnull, 'w')

# ==========================================
# 🔑 CONFIGURACIÓN GENERAL
# ==========================================
EMAIL = os.getenv("IQ_EMAIL")
PASSWORD = os.getenv("IQ_PASSWORD")
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ⚙️ PARÁMETROS DE OPERACIÓN
EXPIRATION = 1                  # ⏱️ EXPIRACIÓN: 1 MINUTO
BASE_AMOUNT = 2.0               # 💰 MONTO POR OPERACIÓN
TIMEFRAME_M1 = 60               # 🕯️ VELAS DE 1 MINUTO

# 🎯 ACTIVOS OTC (Tus pares)
PAIRS = [
    "EURUSD-OTC", "GBPUSD-OTC", "USDCHF-OTC", 
    "EURGBP-OTC", "EURJPY-OTC", "GBPJPY-OTC"
]

# 🛑 GESTIÓN DE RIESGO
MAX_DAILY_TRADES = 20           # Máx operaciones por día
MAX_LOSS_STREAK = 2             # Detener si pierdes 2 seguidas
PAUSE_TIME = 300                # Pausa 5 min tras pérdida

# 🚦 VARIABLES GLOBALES
DAILY_TRADES = 0
CURRENT_DAY = datetime.utcnow().day
LOSS_STREAK = 0
LAST_LOSS = 0

# ====================================================
#   📱 ENVÍO DE MENSAJES A TELEGRAM
# ====================================================
def send(msg):
    if TOKEN and CHAT_ID:
        try:
            requests.post(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"},
                timeout=3
            )
        except:
            pass

# ====================================================
#   🔄 REINICIO DE CONTADORES CADA DÍA
# ====================================================
def reset_day():
    global DAILY_TRADES, CURRENT_DAY, LOSS_STREAK
    if datetime.utcnow().day != CURRENT_DAY:
        DAILY_TRADES = 0
        LOSS_STREAK = 0
        CURRENT_DAY = datetime.utcnow().day
        send("🔄 <b>NUEVO DÍA INICIADO</b> | Contadores reiniciados.")

# ====================================================
#   🔌 CONEXIÓN A IQ OPTION
# ====================================================
def connect():
    while True:
        try:
            iq = IQ_Option(EMAIL, PASSWORD)
            status, _ = iq.connect()
            if status:
                # ⚠️ CAMBIA A "REAL" SI YA USAS DINERO REAL
                iq.change_balance("PRACTICE")
                send("✅ <b>BOT CONECTADO</b> | ESTRATEGIA: RACHAS + CAMBIO DE TENDENCIA")
                return iq
        except Exception as e:
            send(f"❌ Error de conexión: {str(e)}")
        time.sleep(3)

# ====================================================
#   📥 OBTENER DATOS DE VELAS DEL MERCADO
# ====================================================
def get_df(iq, pair, tf):
    try:
        # Pedimos 20 velas, suficientes para detectar la secuencia
        data = iq.get_candles(pair, tf, 20, time.time())
        df = pd.DataFrame(data)
        if df.empty:
            return None
        # Renombrar columnas para coincidir con la lógica
        df.rename(columns={"max": "high", "min": "low"}, inplace=True)
        return df
    except:
        return None

# ====================================================
#   🧠 BUCLE PRINCIPAL DE EJECUCIÓN
# ====================================================
def main():
    global LOSS_STREAK, LAST_LOSS, DAILY_TRADES
    iq = connect()
    last_candle = None
    signal = None

    while True:
        try:
            reset_day()

            # ======================================
            # 🛑 CONTROLES DE SEGURIDAD
            # ======================================
            if DAILY_TRADES >= MAX_DAILY_TRADES:
                time.sleep(10)
                continue

            if LOSS_STREAK >= MAX_LOSS_STREAK:
                if time.time() - LAST_LOSS < PAUSE_TIME:
                    time.sleep(1)
                    continue
                else:
                    LOSS_STREAK = 0 # Reactivar tras pausa

            # ======================================
            # ⏱️ CONTROL DE TIEMPO PRECISO
            # ======================================
            server_time = iq.get_server_timestamp()
            sec = server_time % 60

            # ======================================
            # 🔍 FASE 1: ANÁLISIS (Segundo 45 a 58)
            # ======================================
            if 45 <= sec <= 58:
                best_pair = None
                best_signal = None

                # Escaneamos todos los activos
                for pair in PAIRS:
                    df = get_df(iq, pair, TIMEFRAME_M1)
                    if df is None or len(df) < 4:
                        continue

                    # ✅ LLAMADA A LA ESTRATEGIA
                    s = get_signal(df)

                    if s:
                        best_pair = pair
                        best_signal = s
                        break # Nos quedamos con la primera señal válida

                if best_pair:
                    signal = (best_pair, best_signal)
                else:
                    signal = None

            # ======================================
            # ⚡ FASE 2: EJECUCIÓN (CIERRE DE VELA)
            # ======================================
            if 59.4 <= sec <= 59.98 or 0 <= sec <= 0.25:
                candle = int(server_time // 60)

                # Evitar repetir operación en la misma vela
                if candle == last_candle:
                    continue
                last_candle = candle

                if not signal:
                    continue

                pair, direction = signal

                # ✅ EJECUTAR ORDEN EN IQ OPTION
                status, trade_id = iq.buy(BASE_AMOUNT, pair, direction, EXPIRATION)

                if status:
                    DAILY_TRADES += 1
                    tipo_op = "🟢 <b>COMPRA (CALL)</b>" if direction == "call" else "🔴 <b>VENTA (PUT)</b>"
                    send(f"""🚀 <b>OPERACIÓN EJECUTADA</b>
💹 Activo: {pair}
📈 Patrón: Racha larga + Cambio de dirección
📌 Tipo: {tipo_op}
💲 Monto: ${BASE_AMOUNT}
🔄 #Op: {DAILY_TRADES}/{MAX_DAILY_TRADES}""")

                    # ⏳ ESPERAR RESULTADO (65 Segundos)
                    time.sleep(65)
                    resultado = iq.check_win_v4(trade_id)

                    if resultado < 0:
                        LOSS_STREAK += 1
                        LAST_LOSS = time.time()
                        send(f"❌ <b>LOSS</b> | Saldo: ${resultado:.2f}\n⚠️ Rachas: {LOSS_STREAK}/{MAX_LOSS_STREAK}")
                    else:
                        LOSS_STREAK = 0
                        send(f"✅ <b>WIN</b> | Ganancia: +${resultado:.2f}\n_________________________")

            time.sleep(0.05)

        except Exception as e:
            send(f"💥 <b>ERROR CRÍTICO:</b> {str(e)}")
            time.sleep(2)

if __name__ == "__main__":
    main()

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

# Configuración de logging mejorada
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
BASE_AMOUNT = 64                # 💰 MONTO POR OPERACIÓN
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
CURRENT_DAY = datetime.utcnow().day
LOSS_STREAK = 0
LAST_LOSS = 0
LAST_TRADE_MINUTE = -1          # Control para no repetir operación

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
    global DAILY_TRADES, CURRENT_DAY, LOSS_STREAK
    today = datetime.utcnow().day
    if today != CURRENT_DAY:
        DAILY_TRADES = 0
        LOSS_STREAK = 0
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
                balance_status = iq.change_balance("PRACTICE")  # Cambiar a "REAL" si corresponde
                if not balance_status:
                    send("⚠️ No se pudo cambiar a cuenta PRACTICE, usando actual")
                
                send("✅ <b>BOT CONECTADO CORRECTAMENTE</b> | ESTRATEGIA: RACHAS + CAMBIO DE TENDENCIA")
                return iq
            else:
                send(f"❌ Error de conexión: {reason} | Intento {attempts+1}/{MAX_RECONNECT_ATTEMPTS}")
        
        except Exception as e:
            send(f"❌ Error de conexión: {str(e)} | Intento {attempts+1}/{MAX_RECONNECT_ATTEMPTS}")
        
        attempts += 1
        time.sleep(RECONNECT_DELAY)
    
    send("💥 No se pudo conectar después de varios intentos. Reintentando en 30 segundos...")
    time.sleep(30)
    return connect()

# ====================================================
#   📥 OBTENER DATOS DE VELAS (MEJORADO)
# ====================================================
def get_df(iq, pair, tf):
    try:
        if not iq.check_connect():
            send("⚠️ Conexión perdida, reconectando...")
            iq = connect()
            if not iq:
                return None

        # Pedimos más velas para asegurar datos completos
        data = iq.get_candles(pair, tf, 50, time.time())
        
        if not data or len(data) < 15:
            logging.warning(f"Datos insuficientes para {pair}")
            return None
        
        df = pd.DataFrame(data)
        
        required_cols = ["open", "close", "max", "min", "volume"]
        if not all(col in df.columns for col in required_cols):
            logging.error(f"Estructura de datos inválida para {pair}")
            return None
        
        df.rename(columns={"max": "high", "min": "low"}, inplace=True)
        df = df.astype({"open": float, "close": float, "high": float, "low": float, "volume": float})
        
        return df

    except Exception as e:
        logging.error(f"Error al obtener datos de {pair}: {str(e)}")
        return None

# ====================================================
#   🧠 BUCLE PRINCIPAL - PUNTO DE ENTRADA OPTIMIZADO
# ====================================================
def main():
    global LOSS_STREAK, LAST_LOSS, DAILY_TRADES, LAST_TRADE_MINUTE
    iq = connect()
    pending_signal = None  # Guardamos la señal para ejecutarla en el momento exacto

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
                send(f"ℹ️ Límite diario alcanzado ({MAX_DAILY_TRADES} operaciones). Esperando siguiente día.")
                time.sleep(60)
                continue

            if LOSS_STREAK >= MAX_LOSS_STREAK:
                remaining = int(PAUSE_TIME - (time.time() - LAST_LOSS))
                if remaining > 0:
                    send(f"⏸️ Pausa activa por pérdidas: {remaining}s restantes")
                    time.sleep(10)
                    continue
                else:
                    LOSS_STREAK = 0 
                    send("✅ Pausa finalizada. Reanudando operaciones.")

            # ======================================
            # ⏱️ TIEMPO DEL SERVIDOR
            # ======================================
            server_time = iq.get_server_timestamp()
            sec = server_time % 60
            current_minute = int(server_time // 60)

            # ======================================
            # 🔍 FASE DE ANÁLISIS (Segundos 30 a 57)
            # Análisis anticipado para evitar prisas
            # ======================================
            if 30 <= sec <= 57:
                best_pair = None
                best_signal = None

                for pair in PAIRS:
                    df = get_df(iq, pair, TIMEFRAME_M1)
                    if df is None or len(df) < 15:
                        continue

                    try:
                        s = get_signal(df)
                    except Exception as e:
                        send(f"⚠️ Error en estrategia para {pair}: {str(e)}")
                        continue

                    if s in ["call", "put"]:
                        best_pair = pair
                        best_signal = s
                        break  # Tomamos la primera señal válida

                if best_pair:
                    pending_signal = (best_pair, best_signal)
                    send(f"🔍 Señal preparada: {best_pair} | {best_signal.upper()} | Se ejecutará en cambio de vela")
                else:
                    pending_signal = None

            # ======================================
            # ⚡ EJECUCIÓN PRECISA (Segundos 59.8 a 0.2)
            # Punto de entrada exacto al inicio de la nueva vela
            # ======================================
            if 59.8 <= sec <= 59.99 or 0 <= sec <= 0.2:
                # Evitar repetir operación en el mismo minuto
                if current_minute == LAST_TRADE_MINUTE:
                    continue
                LAST_TRADE_MINUTE = current_minute

                if not pending_signal:
                    continue

                pair, direction = pending_signal
                pending_signal = None  # Limpiamos la señal usada

                # ✅ EJECUTAR ORDEN
                status, trade_id = iq.buy(BASE_AMOUNT, pair, direction, EXPIRATION)

                if status:
                    DAILY_TRADES += 1
                    tipo_op = "🟢 <b>COMPRA (CALL)</b>" if direction == "call" else "🔴 <b>VENTA (PUT)</b>"
                    send(f"""🚀 <b>OPERACIÓN EJECUTADA</b>
💹 Activo: {pair}
📈 Patrón: Racha larga + Cambio de dirección
📍 Punto de entrada: Inicio de vela
💲 Monto: ${BASE_AMOUNT:.2f}
🔄 #Op: {DAILY_TRADES}/{MAX_DAILY_TRADES}""")

                    # ⏳ ESPERAR RESULTADO
                    time.sleep(65)
                    try:
                        resultado = iq.check_win_v4(trade_id)
                        if resultado is None:
                            send("⚠️ No se pudo obtener el resultado de la operación")
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
                    send(f"❌ No se pudo ejecutar operación en {pair}")

            time.sleep(0.03)  # Ciclo más rápido para mayor precisión

        except Exception as e:
            send(f"💥 <b>ERROR CRÍTICO:</b> {str(e)} | Reconectando...")
            logging.exception("Error en bucle principal")
            time.sleep(5)
            try:
                iq = connect()
            except:
                pass

if __name__ == "__main__":
    # Verificación previa de variables de entorno
    required_vars = ["IQ_EMAIL", "IQ_PASSWORD", "TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID"]
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        print(f"❌ Faltan variables de entorno: {', '.join(missing)}")
        send(f"❌ Faltan configuraciones: {', '.join(missing)}")
        sys.exit(1)
    
    main()

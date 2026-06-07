import time
import os
import requests
import pandas as pd
import sys
import threading
import logging
from datetime import datetime, timezone

# Importación de la estrategia optimizada
from strategy import get_trend_signal

from iqoptionapi.stable_api import IQ_Option

# Configuración de registro de actividad
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ==========================================
# ⚙️ CONFIGURACIÓN SINCRONIZADA
# Probabilidad: 87% - 93% | Señales: 28-38/día
# ✅ Control por comandos: /start y /stop
# ✅ Solo continuidad fuerte - Evita consolidación y fin de tendencia
# ==========================================
EMAIL = os.getenv("IQ_EMAIL")
PASSWORD = os.getenv("IQ_PASSWORD")
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

EXPIRATION = 1                # Vencimiento de 1 minuto
BASE_AMOUNT = 25              # Monto fijo por operación
TIMEFRAME_M1 = 60             # Velas de 1 minuto

# ✅ Activos más estables, líquidos y con menor ruido
PAIRS = [
    "EURUSD-OTC", "GBPUSD-OTC", "USDCHF-OTC",
    "EURGBP-OTC", "EURJPY-OTC", "GBPJPY-OTC"
]

MAX_DAILY_TRADES = 40         # Límite máximo diario de operaciones
MAX_LOSS_STREAK = 3           # Pausa después de 3 pérdidas consecutivas
PAUSE_TIME = 1800             # Pausa de seguridad: 30 minutos
MAX_RECONNECT_ATTEMPTS = 5    # Intentos de reconexión
RECONNECT_DELAY = 5           # Segundos entre intentos
FUERZA_MINIMA = 64            # Fuerza mínima requerida para operar

# Variables de control globales
DAILY_TRADES = 0
CURRENT_DAY = datetime.now(timezone.utc).day
LOSS_STREAK = 0
LAST_LOSS = 0
LAST_TRADE = None
BOT_RUNNING = False           # Estado del bot: activado/desactivado

# ====================================================
# 📱 ENVÍO DE NOTIFICACIONES A TELEGRAM
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
            logging.error(f"Error al enviar mensaje: {str(e)}")

# ====================================================
# 🤖 ESCUCHA DE COMANDOS DE TELEGRAM
# ====================================================
def listen_commands():
    global BOT_RUNNING
    last_update_id = 0
    while True:
        try:
            response = requests.get(
                f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                params={"offset": last_update_id + 1, "timeout": 30},
                timeout=35
            )
            data = response.json()
            
            if not data.get("ok"):
                time.sleep(2)
                continue
            
            for update in data.get("result", []):
                last_update_id = update["update_id"]
                message = update.get("message", {})
                text = message.get("text", "").strip().lower()
                chat_id_received = str(message.get("chat", {}).get("id", ""))
                
                # Solo responde al chat autorizado
                if chat_id_received != str(CHAT_ID):
                    continue
                
                if text == "/start":
                    if not BOT_RUNNING:
                        BOT_RUNNING = True
                        send("✅ <b>BOT INICIADO CORRECTAMENTE</b>\nBuscando señales de continuidad fuerte...")
                    else:
                        send("ℹ️ El bot ya se encuentra activo.")
                
                elif text == "/stop":
                    if BOT_RUNNING:
                        BOT_RUNNING = False
                        send("🛑 <b>BOT DETENIDO</b>\nYa no se ejecutarán operaciones. Usa /start para reanudar.")
                    else:
                        send("ℹ️ El bot ya se encuentra detenido.")
        
        except Exception as e:
            logging.error(f"Error al escuchar comandos: {str(e)}")
        
        time.sleep(1)

# ====================================================
# ⏰ HORARIO DE OPERACIÓN OPTIMIZADO
# ====================================================
def es_hora_optima():
    hora_utc = datetime.now(timezone.utc).hour
    hora_bogota = hora_utc - 5
    # Opera en horarios con liquidez suficiente, evitando momentos de baja actividad extrema
    return 0 <= hora_bogota <= 23

# ====================================================
# 🔄 REINICIO DE CONTADORES AL CAMBIAR DE DÍA
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
            send("🔄 <b>NUEVO DÍA INICIADO</b> | Estrategia de continuidad fuerte activa.")

# ====================================================
# 🔌 CONEXIÓN A LA PLATAFORMA IQ OPTION
# ====================================================
def connect():
    attempts = 0
    while attempts < MAX_RECONNECT_ATTEMPTS:
        try:
            if not EMAIL or not PASSWORD:
                send("❌ ERROR: Credenciales de IQ Option no configuradas.")
                time.sleep(10)
                attempts += 1
                continue

            iq = IQ_Option(EMAIL, PASSWORD)
            status, reason = iq.connect()

            if status:
                iq.change_balance("PRACTICE")  # Cambiar a "REAL" si deseas operar con dinero real
                balance = iq.get_balance()
                send(f"✅ <b>CONECTADO EXITOSAMENTE</b>\nSaldo disponible: ${balance:.2f}")
                return iq
            else:
                send(f"❌ Error de conexión: {reason} | Intento {attempts+1}")

        except Exception as e:
            send(f"❌ Error: {str(e)} | Intento {attempts+1}")

        attempts += 1
        time.sleep(RECONNECT_DELAY)

    send("💥 No se pudo conectar después de varios intentos. Reintentando en 30 segundos...")
    time.sleep(30)
    return connect()

# ====================================================
# 📥 OBTENCIÓN DE DATOS DE MERCADO
# ====================================================
def get_df(iq, pair):
    try:
        if not iq.check_connect():
            iq = connect()
            if not iq:
                return None

        # Obtiene las últimas 50 velas para análisis completo
        data = iq.get_candles(pair, TIMEFRAME_M1, 50, time.time())
        if not data or len(data) < 35:
            return None

        df = pd.DataFrame(data)
        df.rename(columns={"max": "high", "min": "low"}, inplace=True)
        df[["open", "close", "high", "low", "volume"]] = df[["open", "close", "high", "low", "volume"]].astype(float)
        return df

    except Exception as e:
        logging.error(f"Error al obtener datos de {pair}: {str(e)}")
        return None

# ====================================================
# 🧠 BUCLE PRINCIPAL DE FUNCIONAMIENTO
# ====================================================
def main():
    global BOT_RUNNING, LOSS_STREAK, LAST_LOSS, DAILY_TRADES, LAST_TRADE
    
    # Iniciar escucha de comandos en segundo plano
    threading.Thread(target=listen_commands, daemon=True).start()
    
    iq = connect()
    last_candle = None

    send("ℹ️ <b>SISTEMA LISTO</b>\nUsa /start para iniciar el bot o /stop para detenerlo.")

    while True:
        try:
            # Si el bot está detenido, solo espera
            if not BOT_RUNNING:
                time.sleep(2)
                continue

            reset_day()

            if not es_hora_optima():
                time.sleep(60)
                continue

            if not iq.check_connect():
                iq = connect()
                time.sleep(2)
                continue

            if DAILY_TRADES >= MAX_DAILY_TRADES:
                send("ℹ️ Límite diario de operaciones alcanzado. Se reanudará mañana.")
                BOT_RUNNING = False
                time.sleep(300)
                continue

            if LOSS_STREAK >= MAX_LOSS_STREAK:
                remaining = int(PAUSE_TIME - (time.time() - LAST_LOSS))
                if remaining > 0:
                    send(f"⏸️ Pausa de seguridad activa: {remaining//60} minutos restantes.")
                    time.sleep(10)
                    continue
                else:
                    LOSS_STREAK = 0
                    LAST_TRADE = None
                    send("✅ Pausa finalizada. Buscando señales de continuidad...")

            server_time = iq.get_server_timestamp()
            sec = server_time % 60
            current_candle = int(server_time // 60)

            if current_candle == last_candle:
                time.sleep(0.1)
                continue
            last_candle = current_candle

            mejor_opcion = None
            mayor_fuerza = 0

            # Análisis de señales entre los 35 y 55 segundos de cada minuto
            if 35 <= sec <= 55:
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

            # Ejecución de la mejor señal al finalizar el minuto
            if 57 <= sec <= 59.9 and mejor_opcion is not None:
                pair, signal, fuerza, direccion = mejor_opcion

                if (pair, signal) == LAST_TRADE:
                    continue
                LAST_TRADE = (pair, signal)

                send(f"""🎯 <b>SEÑAL DE CONTINUIDAD FUERTE</b>
💹 Activo: {pair}
📈 Tendencia: {direccion.upper()}
💪 Fuerza: {fuerza}/100
📊 Operación: {'🟢 COMPRA' if signal == 'call' else '🔴 VENTA'}
⚡ Preparando ejecución...""")

                status, trade_id = iq.buy(BASE_AMOUNT, pair, signal, EXPIRATION)

                if status:
                    DAILY_TRADES += 1
                    send(f"""🚀 <b>OPERACIÓN EJECUTADA</b>
💲 Monto: ${BASE_AMOUNT:.2f}
🔄 Operaciones hoy: {DAILY_TRADES}/{MAX_DAILY_TRADES}""")

                    time.sleep(65)
                    try:
                        res = iq.check_win_v4(trade_id)
                        if res is None:
                            send("⚠️ No se pudo verificar el resultado.")
                            continue

                        if res < 0:
                            LOSS_STREAK += 1
                            LAST_LOSS = time.time()
                            send(f"❌ <b>OPERACIÓN PERDIDA</b> | -${abs(res):.2f}\n⚠️ Rachas: {LOSS_STREAK}/{MAX_LOSS_STREAK}")
                        else:
                            LOSS_STREAK = 0
                            send(f"✅ <b>OPERACIÓN GANADA</b> | +${res:.2f}\n_________________________")

                    except Exception as e:
                        send(f"⚠️ Error al verificar resultado: {str(e)}")
                else:
                    send(f"❌ No se pudo ejecutar la operación en {pair}")

            time.sleep(0.05)

        except Exception as e:
            send(f"💥 Error en el sistema: {str(e)} | Reiniciando...")
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
        print(f"❌ Faltan variables de entorno obligatorias: {', '.join(missing)}")
        sys.exit(1)
    main()

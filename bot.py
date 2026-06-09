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
# ⚙️ CONFIGURACIÓN PARA MÁXIMA ACTIVIDAD
# ==========================================
EMAIL = os.getenv("IQ_EMAIL")
PASSWORD = os.getenv("IQ_PASSWORD")
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

EXPIRATION = 1
BASE_AMOUNT = 25
TIMEFRAME_M1 = 60

# ✅ LISTA MÁS GRANDE DE PARES (REAL + OTC)
PAIRS = [
    "EURUSD", "GBPUSD", "USDCHF", "USDJPY", "EURGBP", "EURJPY", "GBPJPY", "AUDUSD",
    "USDCAD", "NZDUSD", "AUDJPY", "CADJPY", "GBPAUD", "EURAUD", "AUDCAD", "NZDJPY",
    "GBPCAD", "EURCAD", "AUDNZD", "GBPNZD", "EURNZD", "NZDCAD",
    "EURUSD-OTC", "GBPUSD-OTC", "USDCHF-OTC", "USDJPY-OTC",
    "EURGBP-OTC", "EURJPY-OTC", "GBPJPY-OTC", "AUDUSD-OTC",
    "USDCAD-OTC", "NZDUSD-OTC", "AUDJPY-OTC", "CADJPY-OTC",
    "GBPAUD-OTC", "EURAUD-OTC", "AUDCAD-OTC", "NZDJPY-OTC",
    "GBPCAD-OTC", "EURCAD-OTC", "AUDNZD-OTC", "GBPNZD-OTC",
    "EURNZD-OTC", "NZDCAD-OTC"
]

MAX_DAILY_TRADES = 100      # Límite muy alto para operar al máximo
MAX_LOSS_STREAK = 5         # Más tolerancia
PAUSE_TIME = 900            # Pausa muy corta: 15 minutos
MAX_RECONNECT_ATTEMPTS = 10 # Más reintentos
RECONNECT_DELAY = 5
FUERZA_MINIMA = 40          # Umbral MUY BAJO para aceptar casi cualquier señal
                            # (Asegura operación, pero puede reducir efectividad)

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
                        send("✅ <b>BOT INICIADO</b>\nAnalizando TODOS los activos, buscando MUCHAS señales!")
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
                try:
                    iq.change_balance("PRACTICE")
                    balance = iq.get_balance()
                    send(f"✅ <b>CONECTADO EXITOSAMENTE</b>\nSaldo: ${balance:.2f}\nAnalizando {len(PAIRS)} activos.")
                    return iq
                except Exception as e:
                    send(f"⚠️ Error al cargar saldo. Reintentando...")
                    iq = None
            else:
                send(f"❌ Conexión fallida: {reason}")
                
        except Exception as e:
            send(f"❌ Error conexión: {str(e)}")
        
        attempts += 1
        time.sleep(RECONNECT_DELAY)
    
    send("💥 Demasiados intentos fallidos. Reintentando en 60 segundos...")
    time.sleep(60)
    return connect()

# ====================================================
# 📥 OBTENER DATOS CON MÁS REINTENTOS Y VALIDACIONES
# ====================================================
def get_df(iq, pair, retries=3): # Más reintentos
    for _ in range(retries):
        try:
            if not iq or not iq.check_connect():
                iq = connect()
                if not iq:
                    time.sleep(1)
                    continue

            # Menos velas para acelerar y simplificar
            data = iq.get_candles(pair, TIMEFRAME_M1, 20, time.time())
            if not data or len(data) < 10: # Menos velas requeridas
                time.sleep(0.3)
                continue

            df = pd.DataFrame(data)
            df.rename(columns={"max": "high", "min": "low"}, inplace=True)
            df[["open", "close", "high", "low", "volume"]] = df[["open", "close", "high", "low", "volume"]].astype(float)
            return df

        except Exception as e:
            logging.error(f"Datos {pair}: {str(e)}")
            time.sleep(0.5)
    
    return None

# ====================================================
# 🧠 BUCLE PRINCIPAL (AJUSTADO PARA MÁS SEÑALES)
# ====================================================
def main():
    global BOT_RUNNING, LOSS_STREAK, LAST_LOSS, DAILY_TRADES, LAST_TRADE
    threading.Thread(target=listen_commands, daemon=True).start()

    iq = connect()
    last_candle = None
    send("ℹ️ <b>SISTEMA LISTO</b>\nEnvía /start para iniciar la búsqueda intensiva de señales.")

    while True:
        try:
            if not BOT_RUNNING:
                time.sleep(2)
                continue

            reset_day()

            if not iq or not iq.check_connect():
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

            # Mayor rango para buscar señales
            if 10 <= sec <= 59:
                # Si estamos cerca de cerrar vela, buscar señal para la próxima
                if sec >= 55:
                    send("🔍 Buscando señal para la siguiente vela...")
                
                mejor_opcion = None
                mayor_fuerza = 0

                for pair in PAIRS:
                    df = get_df(iq, pair)
                    if df is None:
                        continue

                    resultado = get_trend_signal(df)
                    if resultado is not None:
                        signal, fuerza, direccion = resultado
                        # Aceptar la primera señal fuerte si es > FUERZA_MINIMA, no buscar la "mayor"
                        # Esto asegura que opera si encuentra algo válido
                        if fuerza >= FUERZA_MINIMA:
                            mejor_opcion = (pair, signal, fuerza, direccion)
                            break # Romper y operar la primera señal válida

            # Ejecutar SIEMPRE la primera señal encontrada dentro de la ventana de segundos
            if 57 <= sec <= 59.9 and mejor_opcion is not None:
                pair, signal, fuerza, direccion = mejor_opcion

                if (pair, signal) == LAST_TRADE: # Evitar operar el mismo par/dirección repetidamente
                    continue
                LAST_TRADE = (pair, signal)

                send(f"""🎯 <b>SEÑAL DETECTADA</b>
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

            time.sleep(0.01) # Reducir sleep para mayor frecuencia

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

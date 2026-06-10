import time
import os
import requests
import pandas as pd
import numpy as np
import sys
import threading
import logging
from datetime import datetime, timezone

from strategy import get_reversal_signal
from iqoptionapi.stable_api import IQ_Option

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ==========================================
# ⚙️ CONFIGURACIÓN FINAL - TIEMPOS CORREGIDOS
# ==========================================
EMAIL = os.getenv("IQ_EMAIL")
PASSWORD = os.getenv("IQ_PASSWORD")
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

EXPIRATION = 1
BASE_AMOUNT = 25
TIMEFRAME_M1 = 60

# Solo pares que siempre están activos (evita problemas de mercado cerrado)
PARES = [
    "EURUSD-OTC", "GBPUSD-OTC", "USDCHF-OTC", "USDJPY-OTC",
    "EURGBP-OTC", "EURJPY-OTC", "GBPJPY-OTC", "AUDUSD-OTC",
    "USDCAD-OTC", "NZDUSD-OTC", "AUDJPY-OTC", "CADJPY-OTC",
    "GBPAUD-OTC", "EURAUD-OTC", "AUDCAD-OTC", "NZDJPY-OTC",
    "GBPCAD-OTC", "EURCAD-OTC", "AUDNZD-OTC", "GBPNZD-OTC",
    "EURNZD-OTC", "NZDCAD-OTC"
]

MAX_DAILY_TRADES = 100
MAX_LOSS_STREAK = 5
PAUSE_TIME = 900
MAX_RECONNECT_ATTEMPTS = 10
RECONNECT_DELAY = 3
FUERZA_MINIMA = 40
TOLERANCIA_NIVEL = 0.0012
VENTANA_NIVELES = 6

# ⏱️ TIEMPOS EXACTOS PARA IQ OPTION
REINTENTOS_EJECUCION = 3
ESPERA_ENTRE_INTENTOS = 0.5
TIEMPO_MINIMO_VALIDO = 58  # Requiere al menos 58 segundos restantes

# Variables globales
DAILY_TRADES = 0
CURRENT_DAY = datetime.now(timezone.utc).day
LOSS_STREAK = 0
LAST_LOSS = 0
LAST_TRADE = None
BOT_RUNNING = False
SEÑAL_PENDIENTE = None

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
                        send("✅ <b>BOT INICIADO</b>\n✅ Tiempos corregidos para IQ Option\n✅ Entrada al abrir la vela\nBuscando señales...")
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
    global DAILY_TRADES, CURRENT_DAY, LOSS_STREAK, LAST_TRADE, SEÑAL_PENDIENTE
    today = datetime.now(timezone.utc).day
    if today != CURRENT_DAY:
        DAILY_TRADES = 0
        LOSS_STREAK = 0
        LAST_TRADE = None
        SEÑAL_PENDIENTE = None
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
                send("❌ ERROR: Credenciales no configuradas.")
                time.sleep(10)
                attempts += 1
                continue

            iq = IQ_Option(EMAIL, PASSWORD)
            ok, reason = iq.connect()
            
            if ok:
                try:
                    iq.change_balance("PRACTICE")  # Cambia a "REAL" para operar en vivo
                    balance = iq.get_balance()
                    send(f"✅ <b>CONECTADO</b>\nSaldo: ${balance:.2f}")
                    return iq
                except Exception as e:
                    send(f"⚠️ Cargando datos...")
                    iq = None
            else:
                send(f"❌ Conexión fallida: {reason}")
                
        except Exception as e:
            send(f"❌ Error conexión: {str(e)}")
        
        attempts += 1
        time.sleep(RECONNECT_DELAY)
    
    send("💥 Reintentando en 60s...")
    time.sleep(60)
    return connect()

# ====================================================
# 📥 OBTENER DATOS
# ====================================================
def get_df(iq, par, reintentos=2):
    for _ in range(reintentos):
        try:
            if not iq or not iq.check_connect():
                iq = connect()
                if not iq:
                    time.sleep(1)
                    continue

            datos = iq.get_candles(par, TIMEFRAME_M1, 20, time.time())
            if not datos or len(datos) < 10:
                time.sleep(0.2)
                continue

            df = pd.DataFrame(datos)
            df.rename(columns={"max": "high", "min": "low"}, inplace=True)
            df[["open", "close", "high", "low", "volume"]] = df[["open", "close", "high", "low", "volume"]].astype(float)
            return df

        except Exception as e:
            logging.error(f"Datos {par}: {str(e)}")
            time.sleep(0.3)
    
    return None

# ====================================================
# 🚀 EJECUCIÓN CON VERIFICACIÓN DE TIEMPO
# ====================================================
def ejecutar_operacion_segura(iq, monto, par, direccion, vencimiento):
    """Verifica que haya tiempo suficiente antes de enviar la orden"""
    for intento in range(REINTENTOS_EJECUCION + 1):
        try:
            if not iq.check_connect():
                iq = connect()
                time.sleep(0.3)
            
            # ✅ Verificación CRUCIAL: tiempo restante válido
            tiempo_servidor = iq.get_server_timestamp()
            segundos_restantes = 60 - (tiempo_servidor % 60)
            
            if segundos_restantes < TIEMPO_MINIMO_VALIDO:
                return False, None

            # Enviar orden
            estado, id_operacion = iq.buy(monto, par, direccion, vencimiento)
            
            if estado and id_operacion > 0:
                return True, id_operacion
            
            if intento < REINTENTOS_EJECUCION:
                time.sleep(ESPERA_ENTRE_INTENTOS)

        except Exception as e:
            if intento < REINTENTOS_EJECUCION:
                time.sleep(ESPERA_ENTRE_INTENTOS)
    
    return False, None

# ====================================================
# 🧠 LÓGICA PRINCIPAL
# ====================================================
def main():
    global BOT_RUNNING, LOSS_STREAK, LAST_LOSS, DAILY_TRADES, LAST_TRADE, SEÑAL_PENDIENTE
    threading.Thread(target=listen_commands, daemon=True).start()

    iq = connect()
    ultima_vela = None
    send("ℹ️ <b>SISTEMA LISTO</b>\nEnvía /start para operar.")

    while True:
        try:
            if not BOT_RUNNING:
                time.sleep(1)
                continue

            reset_day()

            if not iq or not iq.check_connect():
                iq = connect()
                time.sleep(1)
                continue

            if DAILY_TRADES >= MAX_DAILY_TRADES:
                send("ℹ️ Límite diario alcanzado.")
                BOT_RUNNING = False
                time.sleep(300)
                continue

            if LOSS_STREAK >= MAX_LOSS_STREAK:
                resto_pausa = int(PAUSE_TIME - (time.time() - LAST_LOSS))
                if resto_pausa > 0:
                    send(f"⏸️ Pausa: {resto_pausa//60} min")
                    time.sleep(5)
                    continue
                else:
                    LOSS_STREAK = 0
                    LAST_TRADE = None
                    send("✅ Pausa finalizada.")

            tiempo_servidor = iq.get_server_timestamp()
            segundos = tiempo_servidor % 60
            vela_actual = int(tiempo_servidor // 60)

            # ==========================================
            # 1. AL ABRIR LA VELA: EJECUTAR SEÑAL PENDIENTE
            # ==========================================
            if vela_actual != ultima_vela:
                ultima_vela = vela_actual

                if SEÑAL_PENDIENTE is not None:
                    par, direccion, fuerza, nivel = SEÑAL_PENDIENTE
                    SEÑAL_PENDIENTE = None

                    if (par, direccion) == LAST_TRADE:
                        continue
                    LAST_TRADE = (par, direccion)

                    send(f"""🚀 <b>ENTRANDO AL ABRIR LA VELA</b>
💹 Activo: {par}
📍 Nivel: {nivel.upper()}
💪 Fuerza: {fuerza}/100
📊 Tipo: {'🟢 COMPRA' if direccion == 'call' else '🔴 VENTA'}
⏱️ Vencimiento: 1 minuto""")

                    exito, id_operacion = ejecutar_operacion_segura(iq, BASE_AMOUNT, par, direccion, EXPIRATION)

                    if exito:
                        DAILY_TRADES += 1
                        send(f"✅ <b>OPERACIÓN ABIERTA</b> | ${BASE_AMOUNT:.2f} | Total: {DAILY_TRADES}/{MAX_DAILY_TRADES}")

                        time.sleep(65)
                        try:
                            resultado = iq.check_win_v4(id_operacion)
                            if resultado is None:
                                send("⚠️ Resultado no verificado.")
                                continue

                            if resultado < 0:
                                LOSS_STREAK += 1
                                LAST_LOSS = time.time()
                                send(f"❌ <b>PERDIDA</b> | -${abs(resultado):.2f}\nRacha: {LOSS_STREAK}/{MAX_LOSS_STREAK}")
                            else:
                                LOSS_STREAK = 0
                                send(f"✅ <b>GANADA</b> | +${resultado:.2f}\n_________________________")

                        except Exception as e:
                            send(f"⚠️ Error al verificar: {str(e)}")
                    else:
                        send(f"❌ No se pudo ejecutar (tiempo insuficiente o mercado cerrado)")

            # ==========================================
            # 2. DETECTAR SEÑALES AL FINAL DE LA VELA
            # ==========================================
            if 52 <= segundos <= 58:
                mejor_señal = None
                mayor_fuerza = 0

                for par in PARES:
                    df = get_df(iq, par)
                    if df is None:
                        continue

                    resultado = get_reversal_signal(df, TOLERANCIA_NIVEL, VENTANA_NIVELES)
                    if resultado is not None:
                        dir_sen, fuerza, nivel = resultado
                        if fuerza >= FUERZA_MINIMA and fuerza > mayor_fuerza:
                            mayor_fuerza = fuerza
                            mejor_señal = (par, dir_sen, fuerza, nivel)

                if 56 <= segundos <= 58 and mejor_señal is not None:
                    SEÑAL_PENDIENTE = mejor_señal
                    par, dir_sen, fuerza, nivel = mejor_señal
                    send(f"""🔍 <b>SEÑAL DETECTADA</b>
💹 Activo: {par}
📍 Nivel: {nivel.upper()}
💪 Fuerza: {fuerza}/100
⏳ Se ejecutará al abrir la siguiente vela""")

            time.sleep(0.02)

        except Exception as e:
            send(f"💥 Error: {str(e)} | Reiniciando...")
            logging.exception("Error principal")
            time.sleep(2)
            try:
                iq = connect()
            except:
                pass

if __name__ == "__main__":
    requeridas = ["IQ_EMAIL", "IQ_PASSWORD", "TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID"]
    faltantes = [var for var in requeridas if not os.getenv(var)]
    if faltantes:
        print(f"❌ Faltan variables: {', '.join(faltantes)}")
        sys.exit(1)
    main()

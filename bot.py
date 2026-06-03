import time
import os
import requests
import pandas as pd
import sys
import logging
from datetime import datetime
import json

from strategy import get_signal

from iqoptionapi.stable_api import IQ_Option

# Ocultar mensajes de error innecesarios
logging.getLogger().setLevel(logging.CRITICAL)
sys.stderr = open(os.devnull, 'w')

# ==========================================
# 🔑 CONFIGURACIÓN
# ==========================================
EMAIL = os.getenv("IQ_EMAIL")
PASSWORD = os.getenv("IQ_PASSWORD")
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

EXPIRATION = 1
BASE_AMOUNT = 8
TIMEFRAME_M1 = 60

PAIRS = [
    "EURUSD-OTC", "GBPUSD-OTC", "USDCHF-OTC", 
    "EURGBP-OTC", "EURJPY-OTC", "GBPJPY-OTC"
]

MAX_DAILY_TRADES = 20
MAX_LOSS_STREAK = 2
PAUSE_TIME = 300

DAILY_TRADES = 0
CURRENT_DAY = datetime.utcnow().day
LOSS_STREAK = 0
LAST_LOSS = 0

# ====================================================
#   📱 NOTIFICACIONES TELEGRAM (CORREGIDO)
# ====================================================
def send(msg):
    if TOKEN and CHAT_ID:
        try:
            # Agregado timeout y manejo de errores de conexión
            requests.post(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"},
                timeout=5
            )
        except requests.exceptions.RequestException as e:
            print(f"Error Telegram: {str(e)}")
        except Exception as e:
            print(f"Error desconocido Telegram: {str(e)}")

# ====================================================
#   🔄 REINICIO DIARIO
# ====================================================
def reset_day():
    global DAILY_TRADES, CURRENT_DAY, LOSS_STREAK
    if datetime.utcnow().day != CURRENT_DAY:
        DAILY_TRADES = 0
        LOSS_STREAK = 0
        CURRENT_DAY = datetime.utcnow().day
        send("🔄 <b>NUEVO DÍA - CONTADORES RESETEADOS</b>")

# ====================================================
#   🔌 CONEXIÓN A IQ OPTION (MEJORADA Y CORREGIDA)
# ====================================================
def connect():
    while True:
        try:
            iq = IQ_Option(EMAIL, PASSWORD)
            status, reason = iq.connect()
            
            if status:
                iq.change_balance("PRACTICE")
                send("✅ <b>CONEXIÓN EXITOSA</b> | Bot activo y funcionando")
                return iq
            else:
                send(f"⚠️ Intento de conexión fallido: {reason}")
                
        except json.JSONDecodeError:
            # ESTE ES EL ERROR QUE APARECE: LO MANEJAMOS AQUÍ
            send("❌ Error de conexión: Datos recibidos inválidos. Reintentando...")
        except Exception as e:
            send(f"❌ Error general de conexión: {str(e)}")
        
        # Esperar antes de volver a intentar
        time.sleep(5)

# ====================================================
#   📥 OBTENER DATOS DE VELAS (MANEJO DE ERRORES)
# ====================================================
def get_df(iq, pair, tf):
    try:
        data = iq.get_candles(pair, tf, 20, time.time())
        
        # Verificar que los datos no estén vacíos ni sean inválidos
        if not data or len(data) < 4:
            return None
            
        df = pd.DataFrame(data)
        
        # Verificar que las columnas necesarias existan
        required_cols = ['open', 'close', 'max', 'min']
        if not all(col in df.columns for col in required_cols):
            return None
            
        df.rename(columns={"max": "high", "min": "low"}, inplace=True)
        return df
        
    except json.JSONDecodeError:
        send(f"⚠️ Datos inválidos recibidos de {pair}. Reintentando...")
        return None
    except Exception as e:
        print(f"Error al obtener datos de {pair}: {str(e)}")
        return None

# ====================================================
#   🧠 BUCLE PRINCIPAL
# ====================================================
def main():
    global LOSS_STREAK, LAST_LOSS, DAILY_TRADES
    iq = connect()
    last_candle = None
    signal = None

    while True:
        try:
            reset_day()

            # Controles de seguridad
            if DAILY_TRADES >= MAX_DAILY_TRADES:
                time.sleep(10)
                continue

            if LOSS_STREAK >= MAX_LOSS_STREAK:
                if time.time() - LAST_LOSS < PAUSE_TIME:
                    time.sleep(1)
                    continue
                else:
                    LOSS_STREAK = 0

            # Obtener tiempo del servidor
            try:
                server_time = iq.get_server_timestamp()
                sec = server_time % 60
            except:
                # Si falla la obtención del tiempo, esperar un poco
                time.sleep(2)
                continue

            # FASE DE ANÁLISIS
            if 45 <= sec <= 58:
                best_pair = None
                best_signal = None

                for pair in PAIRS:
                    df = get_df(iq, pair, TIMEFRAME_M1)
                    if df is None:
                        continue

                    s = get_signal(df)
                    if s:
                        best_pair = pair
                        best_signal = s
                        break

                if best_pair:
                    signal = (best_pair, best_signal)
                else:
                    signal = None

            # FASE DE EJECUCIÓN
            if 59.4 <= sec <= 59.98 or 0 <= sec <= 0.25:
                try:
                    candle = int(server_time // 60)
                except:
                    continue

                if candle == last_candle:
                    continue
                last_candle = candle

                if not signal:
                    continue

                pair, direction = signal

                # Ejecutar operación con manejo de errores
                try:
                    status, trade_id = iq.buy(BASE_AMOUNT, pair, direction, EXPIRATION)
                    
                    if status:
                        DAILY_TRADES += 1
                        tipo_op = "🟢 <b>COMPRA (CALL)</b>" if direction == "call" else "🔴 <b>VENTA (PUT)</b>"
                        send(f"""🚀 <b>OPERACIÓN EJECUTADA</b>
💹 Activo: {pair}
📈 Patrón: Racha + Cambio de tendencia
📌 Tipo: {tipo_op}
💲 Monto: ${BASE_AMOUNT}
🔄 #Op: {DAILY_TRADES}/{MAX_DAILY_TRADES}""")

                        # Esperar resultado
                        time.sleep(65)
                        
                        try:
                            resultado = iq.check_win_v4(trade_id)
                            
                            if resultado < 0:
                                LOSS_STREAK += 1
                                LAST_LOSS = time.time()
                                send(f"❌ <b>LOSS</b> | Saldo: ${resultado:.2f}\n⚠️ Rachas: {LOSS_STREAK}/{MAX_LOSS_STREAK}")
                            else:
                                LOSS_STREAK = 0
                                send(f"✅ <b>WIN</b> | Ganancia: +${resultado:.2f}\n_________________________")
                                
                        except Exception as e:
                            send(f"⚠️ No se pudo obtener el resultado de la operación: {str(e)}")
                            
                except Exception as e:
                    send(f"⚠️ No se pudo ejecutar la operación: {str(e)}")

            time.sleep(0.05)

        except json.JSONDecodeError:
            # AQUÍ SE CORRIGE EL ERROR QUE TE APARECE
            send("🔄 Recuperando conexión con el servidor...")
            iq = connect()
            time.sleep(3)
            
        except Exception as e:
            send(f"💥 Error inesperado: {str(e)}")
            time.sleep(3)

if __name__ == "__main__":
    main()

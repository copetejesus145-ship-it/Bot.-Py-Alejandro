import time
import os
import requests
import pandas as pd
import sys
import logging
from datetime import datetime

from iqoptionapi.stable_api import IQ_Option

logging.getLogger().setLevel(logging.CRITICAL)
sys.stderr = open(os.devnull, 'w')

EMAIL = os.getenv("IQ_EMAIL")
PASSWORD = os.getenv("IQ_PASSWORD")
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

EXPIRATION = 1
BASE_AMOUNT = 1

TIMEFRAME_M1 = 60
TIMEFRAME_M5 = 300

PAIRS = [
    "EURUSD-OTC", "GBPUSD-OTC", "USDCHF-OTC", "EURGBP-OTC", "EURJPY-OTC",
    "GBPJPY-OTC", "AUDUSD-OTC", "USDCAD-OTC",
    "EURCAD-OTC", "GBPCAD-OTC", "AUDJPY-OTC", "CADJPY-OTC", "CHFJPY-OTC"
]


# ====================================================
#   ✔ TEMPORAL: ERES LIBRE DE REEMPLAZAR LUEGO
# ====================================================
class RiskManager:
    def __init__(self):
        self.daily = 0
        self.max_daily = 100

    def can_trade(self):
        return self.daily < self.max_daily

    def register_trade(self):
        self.daily += 1


def get_signal(df1, df5):
    """
    Señal simple temporal para que no falle el bot.
    (Luego la reemplazaré por tu estrategia PRO)
    """
    last = df1.iloc[-1]
    if last["close"] > last["open"]:
        return "call"
    else:
        return "put"


def score_market(df1, df5):
    """
    Puntuación simple para no romper el bot.
    Luego la reemplazo por tu sistema PRO.
    """
    rng = abs(df1["close"].iloc[-1] - df1["open"].iloc[-1])
    return 7 if rng > 0 else 3


# ====================================================
#   ✔ FIN DE MÓDULOS TEMPORALES
# ====================================================


DAILY_TRADES = 0
MAX_DAILY_TRADES = 100
CURRENT_DAY = datetime.utcnow().day

LOSS_STREAK = 0
MAX_LOSS_STREAK = 1
PAUSE_TIME = 300
LAST_LOSS = 0

last_best_pair = None
last_best_signal = None


def send(msg):
    if TOKEN and CHAT_ID:
        try:
            requests.post(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                data={"chat_id": CHAT_ID, "text": msg},
                timeout=3
            )
        except:
            pass


def reset_day():
    global DAILY_TRADES, CURRENT_DAY
    if datetime.utcnow().day != CURRENT_DAY:
        DAILY_TRADES = 0
        CURRENT_DAY = datetime.utcnow().day


def connect():
    while True:
        try:
            iq = IQ_Option(EMAIL, PASSWORD)
            status, _ = iq.connect()
            if status:
                iq.change_balance("PRACTICE")
                send("🔥 BOT INSTITUCIONAL PRO ACTIVO")
                return iq
        except:
            pass
        time.sleep(3)


def get_df(iq, pair, tf):
    try:
        data = iq.get_candles(pair, tf, 120, time.time())
        df = pd.DataFrame(data)
        if df.empty:
            return None
        df.rename(columns={"max": "high", "min": "low"}, inplace=True)
        return df
    except:
        return None


def candle_quality(df):
    last = df.iloc[-1]

    body = abs(last["open"] - last["close"])
    wick_up = last["high"] - max(last["open"], last["close"])
    wick_down = min(last["open"], last["close"]) - last["low"]

    if wick_up > body * 1.5:
        return False
    if wick_down > body * 1.5:
        return False
    if body < ((last["high"] - last["low"]) * 0.25):
        return False

    return True


def main():
    global LOSS_STREAK, LAST_LOSS, DAILY_TRADES
    global last_best_pair, last_best_signal

    iq = connect()
    risk = RiskManager()

    last_candle = None
    signal = None

    while True:
        try:
            reset_day()

            if DAILY_TRADES >= MAX_DAILY_TRADES:
                time.sleep(5)
                continue

            if LOSS_STREAK >= MAX_LOSS_STREAK:
                if time.time() - LAST_LOSS < PAUSE_TIME:
                    continue
                else:
                    LOSS_STREAK = 0

            server_time = iq.get_server_timestamp()
            sec = server_time % 60

            if 45 <= sec <= 58:
                best_score = 0
                best_pair = None
                best_signal = None

                for pair in PAIRS:
                    df1 = get_df(iq, pair, TIMEFRAME_M1)
                    df5 = get_df(iq, pair, TIMEFRAME_M5)

                    if df1 is None or df5 is None:
                        continue

                    if not candle_quality(df1):
                        continue

                    score = score_market(df1, df5)

                    if score < 3:
                        continue

                    s = get_signal(df1, df5)

                    if s and score > best_score:
                        best_score = score
                        best_pair = pair
                        best_signal = s

                if best_pair:
                    last_best_pair = best_pair
                    last_best_signal = best_signal
                    signal = (best_pair, best_signal)

            if 59.4 <= sec <= 59.98 or 0 <= sec <= 0.25:
                candle = int(server_time // 60)

                if candle == last_candle:
                    continue
                last_candle = candle

                if not signal:
                    continue

                pair, direction = signal

                direction = "put" if direction == "call" else "call"

                if not risk.can_trade():
                    continue

                status, trade_id = iq.buy(BASE_AMOUNT, pair, direction, EXPIRATION)

                if status:
                    DAILY_TRADES += 1

                    tipo = "COMPRA" if direction == "call" else "VENTA"
                    send(f"⚡ {pair} {tipo} ({DAILY_TRADES}/10)")

                    risk.register_trade()

                    time.sleep(65)
                    result = iq.check_win_v4(trade_id)

                    if result < 0:
                        LOSS_STREAK += 1
                        LAST_LOSS = time.time()
                        send(f"❌ LOSS {LOSS_STREAK}")
                    else:
                        LOSS_STREAK = 0
                        send("✅ WIN")

            time.sleep(0.05)

        except Exception as e:
            print("Error:", e)
            time.sleep(2)


if __name__ == "__main__":
    main()

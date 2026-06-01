import numpy as np

# ============================================
#         PRICE ACTION SIN INDICADORES
# ============================================

# ---------------- SOPORTE / RESISTENCIA ----------------

def near_sr(df):

    last = df.iloc[-1]
    close = last["close"]

    high_zone = df["high"].rolling(50).max().iloc[-2]
    low_zone = df["low"].rolling(50).min().iloc[-2]

    # cerca soporte/resistencia
    if abs(close - high_zone) < (high_zone - low_zone) * 0.05:
        return True

    if abs(close - low_zone) < (high_zone - low_zone) * 0.05:
        return True

    return False

# ---------------- AGOTAMIENTO ----------------

def exhaustion(df):

    move = abs(df["close"].iloc[-1] - df["close"].iloc[-8])

    rango = df["high"].max() - df["low"].min()

    # movimiento extendido
    return move > rango * 0.25

# ---------------- RECHAZO DE ZONAS ----------------

def rejection(df, direction):

    last = df.iloc[-1]
    body = abs(last["close"] - last["open"])

    upper = last["high"] - max(last["open"], last["close"])
    lower = min(last["open"], last["close"]) - last["low"]

    if body == 0:
        return False

    # lógica invertida
    if direction == "call" and lower > body * 1.2:
        return True

    if direction == "put" and upper > body * 1.2:
        return True

    return False

# ---------------- CONTINUIDAD ----------------

def strong_candle(c):

    body = abs(c["close"] - c["open"])
    rango = c["high"] - c["low"]

    if rango == 0:
        return False

    return (body / rango) > 0.6


def continuation(df, direction):

    last = df.iloc[-1]
    prev = df.iloc[-2]

    # CONTINUIDAD INVERTIDA

    if direction == "call":

        if (
            last["close"] < last["open"] and
            prev["close"] > prev["open"] and
            last["close"] < prev["low"] and
            strong_candle(last)
        ):
            return True

    if direction == "put":

        if (
            last["close"] > last["open"] and
            prev["close"] < prev["open"] and
            last["close"] > prev["high"] and
            strong_candle(last)
        ):
            return True

    return False

# ---------------- DIRECCIÓN PRINCIPAL ----------------
# INVERTIDA

def trend_direction(df):

    last = df.iloc[-1]
    prev = df.iloc[-2]

    # rompió arriba -> PUT
    if last["close"] > prev["high"]:
        return "put"

    # rompió abajo -> CALL
    if last["close"] < prev["low"]:
        return "call"

    return None

# ---------------- SEÑAL FINAL ----------------

def pro_signal(df):

    # datos insuficientes
    if len(df) < 160:
        return None

    direction = trend_direction(df)

    if direction is None:
        return None

    # evitar zonas
    if near_sr(df):
        return None

    # evitar agotamiento
    if exhaustion(df):
        return None

    # verificar continuidad
    if not continuation(df, direction):
        return None

    # rechazo fuerte invalida la entrada
    if rejection(df, direction):
        return None

    return direction

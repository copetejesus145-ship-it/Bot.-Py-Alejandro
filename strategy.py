import numpy as np
import pandas as pd

# ==================================================
# 🚀 ESTRATEGIA COMPATIBLE Y FLEXIBLE
# ✅ Sin errores
# ✅ Encuentra muchas señales
# ==================================================

def get_trend_signal(df):
    if len(df) < 15:
        return None

    df = df.copy()

    # Indicadores estables y compatibles
    df['ema8'] = df['close'].ewm(span=8, adjust=False).mean()
    df['ema13'] = df['close'].ewm(span=13, adjust=False).mean()
    df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()

    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean().replace(0, 0.001)
    rs = avg_gain / avg_loss
    df['rsi'] = 100.0 - (100.0 / (1.0 + rs))

    df['macd'] = df['ema13'] - df['ema21']
    df['signal'] = df['macd'].ewm(span=9, adjust=False).mean()

    try:
        e8_1 = float(df['ema8'].iloc[-1])
        e13_1 = float(df['ema13'].iloc[-1])
        e21_1 = float(df['ema21'].iloc[-1])

        c1 = float(df['close'].iloc[-1])
        c2 = float(df['close'].iloc[-2])
        o1 = float(df['open'].iloc[-1])

        macd1 = float(df['macd'].iloc[-1])
        sig1 = float(df['signal'].iloc[-1])
        rsi1 = float(df['rsi'].iloc[-1])
        vol1 = float(df['volume'].iloc[-1])
        vol_prom = float(df['volume'].iloc[-8:-1].mean())

    except Exception:
        return None

    fuerza = 0
    senal = None
    tipo = ""

    # Condición COMPRA
    cond_compra = (
        e8_1 > e13_1 and
        e13_1 > e21_1 and
        macd1 > sig1 and
        40.0 < rsi1 < 75.0 and
        c1 > o1
    )

    if cond_compra:
        senal = "call"
        tipo = "alcista"
        fuerza = 50
        if c1 > c2:
            fuerza += 5
        if vol1 >= vol_prom * 0.5:
            fuerza += 5

    # Condición VENTA
    cond_venta = (
        e8_1 < e13_1 and
        e13_1 < e21_1 and
        macd1 < sig1 and
        25.0 < rsi1 < 60.0 and
        c1 < o1
    )

    if cond_venta:
        senal = "put"
        tipo = "bajista"
        fuerza = 50
        if c1 < c2:
            fuerza += 5
        if vol1 >= vol_prom * 0.5:
            fuerza += 5

    if senal is None:
        return None

    return (senal, min(fuerza, 100), tipo)

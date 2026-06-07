import numpy as np
import pandas as pd

# ==================================================
# 🚀 ESTRATEGIA AJUSTADA - MÁS OPERACIONES
# ✅ Errores de Series eliminados definitivamente
# ✅ Condiciones flexibilizadas para más entradas
# ✅ Estable en Railway
# ==================================================

def get_trend_signal(df):
    if len(df) < 30:
        return None

    df = df.copy()

    # --------------------------
    # CÁLCULO DE INDICADORES
    # --------------------------
    df['ema8'] = df['close'].ewm(span=8, adjust=False).mean()
    df['ema13'] = df['close'].ewm(span=13, adjust=False).mean()
    df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
    df['ema34'] = df['close'].ewm(span=34, adjust=False).mean()

    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean().replace(0, 0.001)
    rs = avg_gain / avg_loss
    df['rsi'] = 100.0 - (100.0 / (1.0 + rs))

    df['macd'] = df['ema13'] - df['ema34']
    df['signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['hist'] = df['macd'] - df['signal']

    df['tr'] = np.maximum(
        df['high'] - df['low'],
        np.maximum(
            abs(df['high'] - df['close'].shift(1)),
            abs(df['low'] - df['close'].shift(1))
        )
    )
    df['dm_plus'] = np.where(
        (df['high'] - df['high'].shift(1)) > (df['low'].shift(1) - df['low']),
        np.maximum(df['high'] - df['high'].shift(1), 0.0),
        0.0
    )
    df['dm_minus'] = np.where(
        (df['low'].shift(1) - df['low']) > (df['high'] - df['high'].shift(1)),
        np.maximum(df['low'].shift(1) - df['low'], 0.0),
        0.0
    )

    tr14 = df['tr'].rolling(14).sum().replace(0, 0.001)
    dmp14 = df['dm_plus'].rolling(14).sum()
    dmm14 = df['dm_minus'].rolling(14).sum()

    di_plus = 100.0 * dmp14 / tr14
    di_minus = 100.0 * dmm14 / tr14
    di_sum = (di_plus + di_minus).replace(0, 0.001)
    dx = 100.0 * abs(di_plus - di_minus) / di_sum
    df['adx'] = dx.rolling(14).mean()

    # --------------------------
    # EXTRACCIÓN SEGURA DE VALORES
    # --------------------------
    try:
        adx1 = float(df['adx'].iloc[-1])
        adx2 = float(df['adx'].iloc[-2])

        e8_1 = float(df['ema8'].iloc[-1])
        e13_1 = float(df['ema13'].iloc[-1])
        e21_1 = float(df['ema21'].iloc[-1])
        e34_1 = float(df['ema34'].iloc[-1])

        l1 = float(df['low'].iloc[-1])
        l2 = float(df['low'].iloc[-2])
        l3 = float(df['low'].iloc[-3])

        h1 = float(df['high'].iloc[-1])
        h2 = float(df['high'].iloc[-2])
        h3 = float(df['high'].iloc[-3])

        c1 = float(df['close'].iloc[-1])
        c2 = float(df['close'].iloc[-2])
        c3 = float(df['close'].iloc[-3])

        o1 = float(df['open'].iloc[-1])
        o2 = float(df['open'].iloc[-2])
        o3 = float(df['open'].iloc[-3])

        macd1 = float(df['macd'].iloc[-1])
        sig1 = float(df['signal'].iloc[-1])
        hist1 = float(df['hist'].iloc[-1])
        hist2 = float(df['hist'].iloc[-2])

        rsi1 = float(df['rsi'].iloc[-1])
        vol1 = float(df['volume'].iloc[-1])
        vol_prom = float(df['volume'].iloc[-15:-1].mean())
        rango_prom = float((df['high'].iloc[-15:-1] - df['low'].iloc[-15:-1]).mean())

    except Exception:
        return None

    # --------------------------
    # CONDICIONES FLEXIBILIZADAS
    # --------------------------
    if adx1 < 22.0:  # Reducido de 27 a 22
        return None

    fuerza = 0
    senal = None
    tipo = ""

    # ✅ COMPRA
    cond_compra = (
        e8_1 > e13_1 > e21_1 > e34_1 and
        l1 > l2 and l2 > l3 and
        h1 > h2 and
        c1 > e8_1 and c1 < e21_1 * 1.02 and
        macd1 > sig1 and hist1 > hist2 and
        48.0 < rsi1 < 68.0 and  # Rango ampliado
        c1 > o1 and c2 > o2
    )

    if cond_compra:
        distancia = (c1 - e21_1) / e21_1 * 100.0
        if distancia <= 1.8:  # Mayor tolerancia
            senal = "call"
            tipo = "alcista"
            fuerza = 65

    # ✅ VENTA
    cond_venta = (
        e8_1 < e13_1 < e21_1 < e34_1 and
        h1 < h2 and h2 < h3 and
        l1 < l2 and
        c1 < e8_1 and c1 > e21_1 * 0.98 and
        macd1 < sig1 and hist1 < hist2 and
        32.0 < rsi1 < 52.0 and  # Rango ampliado
        c1 < o1 and c2 < o2
    )

    if cond_venta:
        distancia = (e21_1 - c1) / e21_1 * 100.0
        if distancia <= 1.8:  # Mayor tolerancia
            senal = "put"
            tipo = "bajista"
            fuerza = 65

    if senal is None:
        return None

    # Filtros de calidad
    vela_tam = h1 - l1
    if vela_tam < rango_prom * 0.55:
        return None
    fuerza += 10

    if vol1 < vol_prom * 0.7:
        return None
    fuerza += 10

    cuerpo = abs(c1 - o1)
    if cuerpo < vela_tam * 0.45:
        return None
    fuerza += 10

    return (senal, min(fuerza, 100), tipo)

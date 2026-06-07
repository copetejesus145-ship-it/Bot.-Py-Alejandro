import numpy as np
import pandas as pd

# ==================================================
# 🚀 ESTRATEGIA: MÁXIMA PRECISIÓN
# ✅ Solo señales con confirmación completa de tendencia, volumen y momentum
# ==================================================

def get_trend_signal(df):
    """
    Devuelve (señal, fuerza, direccion) o None
    Requisitos extremadamente estrictos para reducir falsas señales al mínimo
    """
    if len(df) < 30:
        return None

    df = df.copy()

    # Medias móviles (confirmación de tendencia)
    df['ema8'] = df['close'].ewm(span=8, adjust=False).mean()
    df['ema13'] = df['close'].ewm(span=13, adjust=False).mean()
    df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()

    # RSI ajustado
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean().replace(0, 0.001)
    rs = avg_gain / avg_loss
    df['rsi'] = 100 - (100 / (1 + rs))

    # MACD (confirmación extra de momentum)
    df['macd'] = df['ema8'] - df['ema21']
    df['signal'] = df['macd'].ewm(span=9, adjust=False).mean()

    ultimas = df.tail(15).copy()
    v1 = ultimas.iloc[-1]
    v2 = ultimas.iloc[-2]
    v3 = ultimas.iloc[-3]
    v4 = ultimas.iloc[-4]

    tendencia = "lateral"
    fuerza_base = 0

    # ✅ TENDENCIA ALCISTA (Reglas estrictas)
    if (
        v1.ema8 > v1.ema13 > v1.ema21 and
        v2.ema8 > v2.ema13 > v2.ema21 and
        v3.ema8 > v3.ema13 > v3.ema21 and
        v1.low > v2.low and v2.low > v3.low and v3.low > v4.low and
        v1.high > v2.high and v2.high > v3.high and v3.high > v4.high and
        v1.close > v1.ema8 and
        v1.macd > v1.signal and v2.macd > v2.signal and
        48 < v1.rsi < 65
    ):
        tendencia = "alcista"
        fuerza_base += 55

    # ✅ TENDENCIA BAJISTA (Reglas estrictas)
    elif (
        v1.ema8 < v1.ema13 < v1.ema21 and
        v2.ema8 < v2.ema13 < v2.ema21 and
        v3.ema8 < v3.ema13 < v3.ema21 and
        v1.high < v2.high and v2.high < v3.high and v3.high < v4.high and
        v1.low < v2.low and v2.low < v3.low and v3.low < v4.low and
        v1.close < v1.ema8 and
        v1.macd < v1.signal and v2.macd < v2.signal and
        35 < v1.rsi < 52
    ):
        tendencia = "bajista"
        fuerza_base += 55

    if tendencia == "lateral":
        return None

    # ✅ FILTROS DE CALIDAD ULTRA EXIGENTES
    rango_prom = (ultimas['high'] - ultimas['low']).mean()
    vol_prom = ultimas['volume'].mean()

    tamaño_vela = v1.high - v1.low
    if tamaño_vela < rango_prom * 0.85:
        return None
    fuerza_base += 10

    if v1.volume < vol_prom * 0.9:
        return None
    fuerza_base += 10

    cuerpo = abs(v1.close - v1.open)
    if cuerpo < tamaño_vela * 0.6:
        return None
    fuerza_base += 10

    # ✅ SECUENCIA DE 4 VELAS CONFIRMANDO DIRECCIÓN
    ultimas_6 = df.tail(6).copy()
    ultimas_6['direccion'] = np.where(ultimas_6['close'] > ultimas_6['open'], 1, -1)
    secuencia = ultimas_6['direccion'].tolist()

    if tendencia == "alcista" and secuencia[-4:] == [1, 1, 1, 1]:
        fuerza_base += 15
        return ("call", min(fuerza_base, 100), "alcista")

    if tendencia == "bajista" and secuencia[-4:] == [-1, -1, -1, -1]:
        fuerza_base += 15
        return ("put", min(fuerza_base, 100), "bajista")

    return None

# Compatibilidad
def pro_signal(df):
    return None

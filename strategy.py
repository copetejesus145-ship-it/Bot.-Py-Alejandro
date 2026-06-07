import numpy as np
import pandas as pd

# ==================================================
# 🚀 ESTRATEGIA: PUNTOS DE ALTA PROBABILIDAD
# ==================================================

def get_trend_signal(df):
    """
    Devuelve (señal, fuerza, direccion) o None
    Solo señales con confirmación total
    """
    if len(df) < 25:
        return None

    df = df.copy()

    # Medias móviles dinámicas
    df['ema8'] = df['close'].ewm(span=8, adjust=False).mean()
    df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()

    # Cálculo RSI
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean().replace(0, 0.001)
    rs = avg_gain / avg_loss
    df['rsi'] = 100 - (100 / (1 + rs))

    ultimas = df.tail(12).copy()
    v1 = ultimas.iloc[-1]
    v2 = ultimas.iloc[-2]
    v3 = ultimas.iloc[-3]

    tendencia = "lateral"
    fuerza_base = 0

    # Tendencia alcista válida
    if (v1.ema8 > v1.ema21 and
        v2.ema8 > v2.ema21 and
        v1.low > v3.low and
        v1.close > v1.ema8 and
        40 < v1.rsi < 70):
        tendencia = "alcista"
        fuerza_base += 45

    # Tendencia bajista válida
    elif (v1.ema8 < v1.ema21 and
          v2.ema8 < v2.ema21 and
          v1.high < v3.high and
          v1.close < v1.ema8 and
          30 < v1.rsi < 60):
        tendencia = "bajista"
        fuerza_base += 45

    if tendencia == "lateral":
        return None

    # Filtros de calidad
    rango_prom = (ultimas['high'] - ultimas['low']).mean()
    vol_prom = ultimas['volume'].mean()

    tamaño_vela = v1.high - v1.low
    if tamaño_vela < rango_prom * 0.6:
        return None
    fuerza_base += 10

    if v1.volume < vol_prom * 0.7:
        return None
    fuerza_base += 10

    cuerpo = abs(v1.close - v1.open)
    if cuerpo < tamaño_vela * 0.45:
        return None
    fuerza_base += 10

    # Secuencia de confirmación
    ultimas_5 = df.tail(5).copy()
    ultimas_5['direccion'] = np.where(ultimas_5['close'] > ultimas_5['open'], 1, -1)
    secuencia = ultimas_5['direccion'].tolist()

    if tendencia == "alcista" and secuencia[-3:] == [1, 1, 1]:
        fuerza_base += 20
        return ("call", min(fuerza_base, 100), "alcista")

    if tendencia == "bajista" and secuencia[-3:] == [-1, -1, -1]:
        fuerza_base += 20
        return ("put", min(fuerza_base, 100), "bajista")

    return None

# Compatibilidad
def pro_signal(df):
    return None

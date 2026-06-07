import numpy as np
import pandas as pd

def get_trend_signal(df):
    if len(df) < 25:
        return None

    df = df.copy()
    df['ema8'] = df['close'].ewm(span=8, adjust=False).mean()
    df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()

    # RSI
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean().replace(0, 0.001)
    rs = avg_gain / avg_loss
    df['rsi'] = 100-(100/(1+rs))

    ultimas = df.tail(12).copy()
    v1, v2, v3 = ultimas.iloc[-1], ultimas.iloc[-2], ultimas.iloc[-3]

    tendencia = "lateral"
    fuerza_base = 0

    # Alcista con soporte dinámico
    if (v1.ema8 > v1.ema21 and
        v2.ema8 > v2.ema21 and
        v1.close > v1.ema8 and
        v1.low > v3.low and
        v1.rsi > 40 and v1.rsi < 70):
        tendencia = "alcista"
        fuerza_base += 45

    # Bajista con resistencia dinámica
    elif (v1.ema8 < v1.ema21 and
          v2.ema8 < v2.ema21 and
          v1.close < v1.ema8 and
          v1.high < v3.high and
          v1.rsi > 30 and v1.rsi < 60):
        tendencia = "bajista"
        fuerza_base += 45

    if tendencia == "lateral":
        return None

    # Filtros de calidad
    rango_prom = (ultimas['high']-ultimas['low']).mean()
    vol_prom = ultimas['volume'].mean()

    if (v1.high-v1.low) < rango_prom * 0.6:
        return None
    fuerza_base += 10

    if v1.volume < vol_prom * 0.7:
        return None
    fuerza_base += 10

    cuerpo = abs(v1.close-v1.open)
    if cuerpo < (v1.high-v1.low) * 0.45:
        return None
    fuerza_base += 10

    # Secuencia confirmada
    secuencia = np.where(df.tail(5)['close'] > df.tail(5)['open'], 1, -1).tolist()

    if tendencia == "alcista" and secuencia[-3:] == [1, 1, 1]:
        fuerza_base += 20
        return ("call", min(fuerza_base, 100), "alcista")

    if tendencia == "bajista" and secuencia[-3:] == [-1, -1, -1]:
        fuerza_base += 20
        return ("put", min(fuerza_base, 100), "bajista")

    return None

def pro_signal(df):
    return None

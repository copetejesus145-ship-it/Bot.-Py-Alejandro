import pandas as pd
import numpy as np

def get_signal(df):
    """
    Estrategia por ESTRUCTURA DE MERCADO
    - Solo devuelve señal si hay cambio real en la estructura
    - Evita señales repetitivas sin fuerza
    """
    if df is None or len(df) < 20:
        return None

    data = df.copy()

    # Indicadores
    data['ma_rapida'] = data['close'].rolling(window=5).mean()
    data['ma_lenta'] = data['close'].rolling(window=15).mean()
    data['rango'] = data['high'] - data['low']
    rango_promedio = data['rango'].tail(10).mean()

    # Últimas 4 velas para ver contexto
    ultimas = data.tail(4).copy()
    if len(ultimas) < 4:
        return None

    vela_3 = ultimas.iloc[0]
    vela_2 = ultimas.iloc[1]
    vela_1 = ultimas.iloc[2]
    vela_actual = ultimas.iloc[3]

    # Niveles clave
    resistencia = max(vela_3['high'], vela_2['high'], vela_1['high'])
    soporte = min(vela_3['low'], vela_2['low'], vela_1['low'])

    # Fuerza mínima requerida
    fuerza_minima = rango_promedio * 0.5

    # Señal CALL
    condicion_call = False
    if (
        (vela_actual['low'] <= soporte and 
         (vela_actual['close'] - vela_actual['low']) > fuerza_minima and
         vela_actual['close'] > vela_actual['open'])
        or
        (vela_actual['close'] > resistencia and
         vela_actual['close'] > vela_actual['ma_rapida'] and
         vela_actual['ma_rapida'] > vela_actual['ma_lenta'] and
         (vela_actual['high'] - vela_actual['open']) > fuerza_minima)
    ):
        condicion_call = True

    # Señal PUT
    condicion_put = False
    if (
        (vela_actual['high'] >= resistencia and
         (vela_actual['high'] - vela_actual['close']) > fuerza_minima and
         vela_actual['close'] < vela_actual['open'])
        or
        (vela_actual['close'] < soporte and
         vela_actual['close'] < vela_actual['ma_rapida'] and
         vela_actual['ma_rapida'] < vela_actual['ma_lenta'] and
         (vela_actual['open'] - vela_actual['low']) > fuerza_minima)
    ):
        condicion_put = True

    # Evitamos señales ambiguas
    if condicion_call and not condicion_put:
        return "call"
    elif condicion_put and not condicion_call:
        return "put"
    else:
        return None

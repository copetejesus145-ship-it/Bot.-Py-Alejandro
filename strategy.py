import pandas as pd
import numpy as np

def get_signal(df):
    """
    Estrategia de ALTA PRECISIÓN para expiración 1 minuto
    Analiza: Estructura, soporte/resistencia, volatilidad, fuerza y tendencia
    Devuelve: señal + porcentaje de confianza
    """
    if df is None or len(df) < 30:
        return None, 0

    data = df.copy()

    # ======================================
    # INDICADORES TÉCNICOS
    # ======================================
    # Medias móviles para tendencia
    data['ma_rapida'] = data['close'].rolling(window=5).mean()
    data['ma_media'] = data['close'].rolling(window=10).mean()
    data['ma_lenta'] = data['close'].rolling(window=20).mean()
    
    # Rango verdadero y volatilidad
    data['rango'] = data['high'] - data['low']
    data['rango_promedio'] = data['rango'].rolling(window=15).mean()
    data['volatilidad'] = np.where(data['rango'] > data['rango_promedio'] * 0.7, 1, 0)
    
    # Fuerza de la vela
    data['cuerpo'] = abs(data['close'] - data['open'])
    data['fuerza'] = np.where(data['cuerpo'] > data['rango_promedio'] * 0.4, 1, 0)

    # Últimas 5 velas para análisis completo
    ultimas = data.tail(5).copy()
    if len(ultimas) < 5:
        return None, 0

    vela_4 = ultimas.iloc[0]
    vela_3 = ultimas.iloc[1]
    vela_2 = ultimas.iloc[2]
    vela_1 = ultimas.iloc[3]
    vela_actual = ultimas.iloc[4]

    # ======================================
    # NIVELES CLAVE
    # ======================================
    resistencia = max(vela_4['high'], vela_3['high'], vela_2['high'], vela_1['high'])
    soporte = min(vela_4['low'], vela_3['low'], vela_2['low'], vela_1['low'])
    rango_medio = (resistencia + soporte) / 2

    confianza = 0

    # ======================================
    # CONDICIONES DE COMPRA (CALL)
    # ======================================
    condicion_call = False
    if (
        # Rechazo fuerte en soporte
        (vela_actual['low'] <= soporte and
         vela_actual['close'] > vela_actual['open'] and
         (vela_actual['close'] - vela_actual['low']) > vela_actual['rango'] * 0.6 and
         vela_actual['fuerza'] == 1)
        or
        # Ruptura clara de resistencia con volatilidad
        (vela_actual['close'] > resistencia and
         vela_actual['high'] > resistencia and
         vela_actual['ma_rapida'] > vela_actual['ma_media'] and
         vela_actual['ma_media'] > vela_actual['ma_lenta'] and
         vela_actual['volatilidad'] == 1 and
         vela_actual['fuerza'] == 1)
    ):
        condicion_call = True
        confianza = 85
        # Aumentamos confianza si coincide con tendencia mayor
        if vela_actual['ma_rapida'] > vela_actual['ma_lenta']:
            confianza += 10

    # ======================================
    # CONDICIONES DE VENTA (PUT)
    # ======================================
    condicion_put = False
    if (
        # Rechazo fuerte en resistencia
        (vela_actual['high'] >= resistencia and
         vela_actual['close'] < vela_actual['open'] and
         (vela_actual['high'] - vela_actual['close']) > vela_actual['rango'] * 0.6 and
         vela_actual['fuerza'] == 1)
        or
        # Ruptura clara de soporte
        (vela_actual['close'] < soporte and
         vela_actual['low'] < soporte and
         vela_actual['ma_rapida'] < vela_actual['ma_media'] and
         vela_actual['ma_media'] < vela_actual['ma_lenta'] and
         vela_actual['volatilidad'] == 1 and
         vela_actual['fuerza'] == 1)
    ):
        condicion_put = True
        confianza = 85
        if vela_actual['ma_rapida'] < vela_actual['ma_lenta']:
            confianza += 10

    # ======================================
    # DEVOLVER RESULTADO
    # ======================================
    if condicion_call and not condicion_put:
        return "call", min(confianza, 98)
    elif condicion_put and not condicion_call:
        return "put", min(confianza, 98)
    else:
        return None, 0

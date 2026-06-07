import pandas as pd
import numpy as np

def get_signal(df):
    """
    Estrategia EQUILIBRADA: Más operaciones + buen porcentaje de aciertos
    Expiración: 1 minuto
    """
    if df is None or len(df) < 20:
        return None, 0

    data = df.copy()

    # ======================================
    # INDICADORES
    # ======================================
    data['ma_rapida'] = data['close'].rolling(window=4).mean()
    data['ma_lenta'] = data['close'].rolling(window=12).mean()
    
    data['rango'] = data['high'] - data['low']
    rango_promedio = data['rango'].rolling(window=10).mean()
    
    data['cuerpo'] = abs(data['close'] - data['open'])
    # Bajamos el requisito de fuerza
    data['fuerza'] = np.where(data['cuerpo'] > rango_promedio * 0.25, 1, 0)

    # Últimas 4 velas
    ultimas = data.tail(4).copy()
    if len(ultimas) < 4:
        return None, 0

    vela_3 = ultimas.iloc[0]
    vela_2 = ultimas.iloc[1]
    vela_1 = ultimas.iloc[2]
    vela_actual = ultimas.iloc[3]

    # Niveles clave
    resistencia = max(vela_3['high'], vela_2['high'], vela_1['high'])
    soporte = min(vela_3['low'], vela_2['low'], vela_1['low'])

    confianza = 0

    # ======================================
    # CONDICIONES DE COMPRA (CALL)
    # ======================================
    condicion_call = False
    if (
        # Rechazo en soporte
        (vela_actual['low'] <= soporte and
         vela_actual['close'] > vela_actual['open'] and
         vela_actual['fuerza'] == 1)
        or
        # Ruptura de resistencia
        (vela_actual['close'] > resistencia and
         vela_actual['ma_rapida'] > vela_actual['ma_lenta'])
        or
        # Continuación de tendencia alcista
        (vela_actual['close'] > vela_actual['open'] and
         vela_1['close'] > vela_1['open'] and
         vela_actual['close'] > vela_actual['ma_rapida'])
    ):
        condicion_call = True
        confianza = 65
        if vela_actual['ma_rapida'] > vela_actual['ma_lenta']:
            confianza += 10

    # ======================================
    # CONDICIONES DE VENTA (PUT)
    # ======================================
    condicion_put = False
    if (
        # Rechazo en resistencia
        (vela_actual['high'] >= resistencia and
         vela_actual['close'] < vela_actual['open'] and
         vela_actual['fuerza'] == 1)
        or
        # Ruptura de soporte
        (vela_actual['close'] < soporte and
         vela_actual['ma_rapida'] < vela_actual['ma_lenta'])
        or
        # Continuación de tendencia bajista
        (vela_actual['close'] < vela_actual['open'] and
         vela_1['close'] < vela_1['open'] and
         vela_actual['close'] < vela_actual['ma_rapida'])
    ):
        condicion_put = True
        confianza = 65
        if vela_actual['ma_rapida'] < vela_actual['ma_lenta']:
            confianza += 10

    # ======================================
    # RESULTADO
    # ======================================
    if condicion_call and not condicion_put:
        return "call", min(confianza, 90)
    elif condicion_put and not condicion_call:
        return "put", min(confianza, 90)
    else:
        return None, 0

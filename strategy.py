import pandas as pd
import numpy as np

def get_signal(df):
    """
    Estrategia por ESTRUCTURA DE MERCADO
    Analiza:
    - Niveles de soporte y resistencia
    - Fuerza del movimiento
    - Rupturas o rechazos de niveles clave
    - Volatilidad del activo
    - No usa conteo fijo de velas, solo comportamiento del precio
    """
    if df is None or len(df) < 20:
        return None

    # Trabajamos con todo el historial disponible para ver la estructura
    data = df.copy()

    # ======================================
    # 1. INDICADORES PARA MEDIR ESTRUCTURA
    # ======================================
    # Medias móviles para ver tendencia general
    data['ma_rapida'] = data['close'].rolling(window=5).mean()
    data['ma_lenta'] = data['close'].rolling(window=15).mean()
    
    # Rango verdadero para medir volatilidad
    data['rango'] = data['high'] - data['low']
    rango_promedio = data['rango'].tail(10).mean()

    # Últimas 3 velas cerradas para ver comportamiento reciente
    ultimas = data.tail(3).copy()
    if len(ultimas) < 3:
        return None

    vela_anterior_2 = ultimas.iloc[0]
    vela_anterior_1 = ultimas.iloc[1]
    vela_actual = ultimas.iloc[2]

    # ======================================
    # 2. DETECCIÓN DE NIVELES CLAVE
    # ======================================
    # Soporte y resistencia locales
    resistencia = max(vela_anterior_2['high'], vela_anterior_1['high'])
    soporte = min(vela_anterior_2['low'], vela_anterior_1['low'])

    # ======================================
    # 3. CONDICIONES DE ESTRUCTURA
    # ======================================
    # Señal CALL (SUBE): Rechazo en soporte o ruptura de resistencia con fuerza
    condicion_call = False
    if (
        # Rechazo en zona de soporte
        (vela_actual['low'] <= soporte and vela_actual['close'] > vela_actual['open'] and 
         (vela_actual['close'] - vela_actual['low']) > (rango_promedio * 0.6))
        or
        # Ruptura de resistencia con volumen/fuerza
        (vela_actual['high'] > resistencia and vela_actual['close'] > resistencia and
         vela_actual['close'] > vela_actual['ma_rapida'] and
         vela_actual['ma_rapida'] > vela_actual['ma_lenta'])
    ):
        condicion_call = True

    # Señal PUT (BAJA): Rechazo en resistencia o ruptura de soporte con fuerza
    condicion_put = False
    if (
        # Rechazo en zona de resistencia
        (vela_actual['high'] >= resistencia and vela_actual['close'] < vela_actual['open'] and
         (vela_actual['high'] - vela_actual['close']) > (rango_promedio * 0.6))
        or
        # Ruptura de soporte con fuerza
        (vela_actual['low'] < soporte and vela_actual['close'] < soporte and
         vela_actual['close'] < vela_actual['ma_rapida'] and
         vela_actual['ma_rapida'] < vela_actual['ma_lenta'])
    ):
        condicion_put = True

    # ======================================
    # 4. DEVOLVER SEÑAL
    # ======================================
    if condicion_call and not condicion_put:
        return "call"
    elif condicion_put and not condicion_call:
        return "put"
    else:
        return None

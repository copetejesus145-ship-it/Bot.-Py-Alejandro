import pandas as pd
import numpy as np

def get_signal(df):
    """
    ESTRATEGIA EXACTA: Entrada solo por cierre en soporte o resistencia
    ✅ Solo si cierra en nivel clave
    ✅ Detecta rechazo/reversión
    ✅ Alta probabilidad de cambio en vela siguiente
    """
    if df is None or len(df) < 30:
        return None, 0

    data = df.copy()

    # ======================================
    # INDICADORES
    # ======================================
    data['rango'] = data['high'] - data['low']
    rango_prom = data['rango'].rolling(window=20).mean()
    data['cuerpo'] = abs(data['close'] - data['open'])
    data['direccion'] = np.where(data['close'] > data['open'], 1, -1)

    # Últimas 10 velas para detectar niveles
    ultimas = data.tail(10).copy()
    if len(ultimas) < 10:
        return None, 0

    # ======================================
    # DETECTAR SOPORTE Y RESISTENCIA CLAVE
    # ======================================
    # Resistencia: máximos de las últimas 8 velas
    resistencia = round(ultimas['high'].iloc[:-1].max(), 5)
    # Soporte: mínimos de las últimas 8 velas
    soporte = round(ultimas['low'].iloc[:-1].min(), 5)

    vela_actual = ultimas.iloc[-1]
    cierre = round(vela_actual['close'], 5)
    tolerancia = rango_prom * 0.08  # Margen pequeño para considerar "cierre en nivel"

    confianza = 0

    # ======================================
    # CONDICIÓN 1: CERRO EN SOPORTE → REVERSIÓN AL ALZA
    # ======================================
    if abs(cierre - soporte) <= tolerancia:
        # Rechazo claro: mecha larga inferior + cuerpo pequeño/cierre recuperando
        mecha_inferior = vela_actual['open'] - vela_actual['low'] if vela_actual['close'] > vela_actual['open'] else vela_actual['close'] - vela_actual['low']
        if (
            mecha_inferior > rango_prom * 0.4  # Rechazo fuerte
            and vela_actual['cuerpo'] < rango_prom * 0.6  # No sigue cayendo
            and vela_actual['close'] > vela_actual['open']  # Cierre con compra
        ):
            confianza = 85
            return "call", confianza

    # ======================================
    # CONDICIÓN 2: CERRO EN RESISTENCIA → REVERSIÓN A LA BAJA
    # ======================================
    if abs(cierre - resistencia) <= tolerancia:
        # Rechazo claro: mecha larga superior + cuerpo pequeño/cierre retrocediendo
        mecha_superior = vela_actual['high'] - vela_actual['close'] if vela_actual['close'] < vela_actual['open'] else vela_actual['high'] - vela_actual['open']
        if (
            mecha_superior > rango_prom * 0.4  # Rechazo fuerte
            and vela_actual['cuerpo'] < rango_prom * 0.6  # No sigue subiendo
            and vela_actual['close'] < vela_actual['open']  # Cierre con venta
        ):
            confianza = 85
            return "put", confianza

    # ======================================
    # SIN CONDICIÓN VÁLIDA
    # ======================================
    return None, 0

import pandas as pd
import numpy as np

def get_signal(df):
    """
    ESTRATEGIA: Entrada solo por cierre en soporte o resistencia
    ✅ Solo si cierra en nivel clave
    ✅ Detecta rechazo y reversión
    ✅ Alta probabilidad de cambio en vela siguiente
    ✅ Sin errores de comparación
    """
    if df is None or len(df) < 30:
        return None, 0

    data = df.copy()

    # ======================================
    # INDICADORES
    # ======================================
    data['rango'] = data['high'] - data['low']
    rango_prom = data['rango'].rolling(window=20).mean().iloc[-1]  # Solo valor final
    data['cuerpo'] = abs(data['close'] - data['open'])

    # Últimas 10 velas para detectar niveles
    ultimas = data.tail(10).copy()
    if len(ultimas) < 10:
        return None, 0

    # ======================================
    # DETECTAR SOPORTE Y RESISTENCIA
    # ======================================
    # Resistencia: máximo de las 9 velas anteriores
    resistencia = round(ultimas['high'].iloc[:-1].max(), 5)
    # Soporte: mínimo de las 9 velas anteriores
    soporte = round(ultimas['low'].iloc[:-1].min(), 5)

    # Valores de la vela actual
    vela_actual = ultimas.iloc[-1]
    cierre = round(vela_actual['close'], 5)
    apertura = vela_actual['open']
    maximo = vela_actual['high']
    minimo = vela_actual['low']
    cuerpo = vela_actual['cuerpo']
    rango_actual = vela_actual['rango']

    # Tolerancia para considerar que cierra en el nivel (8% del rango promedio)
    tolerancia = round(rango_prom * 0.08, 5)

    confianza = 0

    # ======================================
    # CONDICIÓN 1: Cierre en SOPORTE → COMPRA
    # ======================================
    if abs(cierre - soporte) <= tolerancia:
        # Medimos rechazo fuerte
        mecha_inferior = apertura - minimo if cierre > apertura else cierre - minimo
        if (
            mecha_inferior > rango_prom * 0.4  # Rechazo claro
            and cuerpo < rango_prom * 0.7      # No sigue cayendo con fuerza
            and cierre > apertura              # Cierre con presión compradora
        ):
            confianza = 75
            return "call", confianza

    # ======================================
    # CONDICIÓN 2: Cierre en RESISTENCIA → VENTA
    # ======================================
    if abs(cierre - resistencia) <= tolerancia:
        # Medimos rechazo fuerte
        mecha_superior = maximo - cierre if cierre < apertura else maximo - apertura
        if (
            mecha_superior > rango_prom * 0.4  # Rechazo claro
            and cuerpo < rango_prom * 0.7      # No sigue subiendo con fuerza
            and cierre < apertura              # Cierre con presión vendedora
        ):
            confianza = 75
            return "put", confianza

    # ======================================
    # Sin señal válida
    # ======================================
    return None, 0

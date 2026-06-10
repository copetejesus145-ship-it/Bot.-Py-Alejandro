import pandas as pd
import numpy as np

def get_reversal_signal(df, tolerancia=0.0018, ventana=5):
    """
    ESTRATEGIA OPTIMIZADA: Detecta reversiones en soporte y resistencia
    ✅ Analiza cierres en niveles clave
    ✅ Detecta rechazo y mechas
    ✅ Devuelve señal, fuerza y tipo de nivel
    """
    if df is None or len(df) < ventana + 1:
        return None

    data = df.copy()
    data['rango'] = data['high'] - data['low']
    rango_promedio = data['rango'].rolling(window=ventana).mean().iloc[-1]

    if pd.isna(rango_promedio) or rango_promedio <= 0:
        return None

    ultimas = data.tail(ventana + 1).copy()
    if len(ultimas) < ventana + 1:
        return None

    # Cálculo de niveles clave
    resistencia = round(ultimas['high'].iloc[:-1].max(), 5)
    soporte = round(ultimas['low'].iloc[:-1].min(), 5)

    vela_actual = ultimas.iloc[-1]
    cierre = round(vela_actual['close'], 5)
    apertura = vela_actual['open']
    maximo = vela_actual['high']
    minimo = vela_actual['low']
    cuerpo = abs(cierre - apertura)

    # ======================================
    # SEÑAL DE COMPRA: Cierre en soporte + rechazo
    # ======================================
    if abs(cierre - soporte) <= tolerancia:
        mecha_inferior = (apertura - minimo) if cierre > apertura else (cierre - minimo)
        
        if (mecha_inferior > rango_promedio * 0.25 and 
            cuerpo < rango_promedio * 0.8 and 
            cierre > apertura):
            
            fuerza = int(min(95, 40 + (mecha_inferior / rango_promedio) * 60))
            return "call", fuerza, "soporte"

    # ======================================
    # SEÑAL DE VENTA: Cierre en resistencia + rechazo
    # ======================================
    if abs(cierre - resistencia) <= tolerancia:
        mecha_superior = (maximo - cierre) if cierre < apertura else (maximo - apertura)
        
        if (mecha_superior > rango_promedio * 0.25 and 
            cuerpo < rango_promedio * 0.8 and 
            cierre < apertura):
            
            fuerza = int(min(95, 40 + (mecha_superior / rango_promedio) * 60))
            return "put", fuerza, "resistencia"

    return None

import pandas as pd
import numpy as np

def get_reversal_signal(df, tolerancia=0.0018, ventana=5):
    if df is None or len(df) < ventana +1:
        return None

    data = df.copy()
    data['rango'] = data['high'] - data['low']
    rango_prom = data['rango'].rolling(window=ventana).mean().iloc[-1]

    if pd.isna(rango_prom) or rango_prom <=0:
        return None

    ultimas = data.tail(ventana +1)
    resistencia = round(ultimas['high'].iloc[:-1].max(),5)
    soporte = round(ultimas['low'].iloc[:-1].min(),5)

    vela = ultimas.iloc[-1]
    cierre = round(vela['close'],5)
    apertura = vela['open']
    maximo = vela['high']
    minimo = vela['low']
    cuerpo = abs(cierre - apertura)

    # Señal COMPRA
    if abs(cierre - soporte) <= tolerancia:
        mecha_inf = (apertura - minimo) if cierre > apertura else (cierre - minimo)
        if mecha_inf > rango_prom *0.25 and cuerpo < rango_prom *0.8 and cierre > apertura:
            fuerza = int(min(95, 40 + (mecha_inf / rango_prom)*60))
            return "call", fuerza, "soporte"

    # Señal VENTA
    if abs(cierre - resistencia) <= tolerancia:
        mecha_sup = (maximo - cierre) if cierre < apertura else (maximo - apertura)
        if mecha_sup > rango_prom *0.25 and cuerpo < rango_prom *0.8 and cierre < apertura:
            fuerza = int(min(95, 40 + (mecha_sup / rango_prom)*60))
            return "put", fuerza, "resistencia"

    return None

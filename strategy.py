import numpy as np
import pandas as pd

# ==================================================
# 🚀 ESTRATEGIA: RACHAS + LECTURA DE ESTRUCTURA
# ✅ LÓGICA:
# 1. DETECTAR ESTRUCTURA GENERAL DE CADA PAR
# 2. BUSCAR PATRÓN DE RACHA + CAMBIO
# 3. SOLO OPERAR SI LA SEÑAL COINCIDE CON LA ESTRUCTURA
# ==================================================

def get_signal(df):
    if len(df) < 8:  # Necesitamos más velas para ver la estructura
        return None

    # --------------------------
    # 🔍 PASO 1: LEER ESTRUCTURA DEL MERCADO
    # --------------------------
    ultimas_velas = df.tail(8).copy()
    maximos = ultimas_velas['high'].values
    minimos = ultimas_velas['low'].values

    # Detectar tipo de estructura
    estructura = "lateral"
    if maximos[-1] > maximos[-2] > maximos[-3] and minimos[-1] > minimos[-2] > minimos[-3]:
        estructura = "alcista"  # Máximos y mínimos crecientes
    elif maximos[-1] < maximos[-2] < maximos[-3] and minimos[-1] < minimos[-2] < minimos[-3]:
        estructura = "bajista"  # Máximos y mínimos decrecientes

    # --------------------------
    # 📊 PASO 2: CLASIFICAR VELAS Y SECUENCIA
    # --------------------------
    analisis = df.tail(5).copy()
    analisis['tipo'] = np.where(analisis['close'] > analisis['open'], 1, -1)
    secuencia = analisis['tipo'].tolist()

    # Filtro de tamaño mínimo
    rango_prom = df['high'].sub(df['low']).tail(10).mean()
    tamaño_cambio = analisis.iloc[-1]['high'] - analisis.iloc[-1]['low']
    if tamaño_cambio < rango_prom * 0.55:
        return None

    # --------------------------
    # ✅ PASO 3: SEÑALES SEGÚN ESTRUCTURA
    # --------------------------
    # CASO 1: Racha bajista → posible compra
    if secuencia[0] == -1 and secuencia[1] == -1 and secuencia[2] == -1 and secuencia[-1] == 1:
        vela_racha = analisis.iloc[-2]
        vela_cambio = analisis.iloc[-1]
        punto_medio = (vela_racha['high'] + vela_racha['low']) / 2

        # Solo aceptamos si:
        # - La vela confirma el cambio
        # - O estamos en estructura bajista (reversión) o lateral
        if vela_cambio['close'] > punto_medio:
            if estructura in ["bajista", "lateral"]:
                return "call"

    # CASO 2: Racha alcista → posible venta
    if secuencia[0] == 1 and secuencia[1] == 1 and secuencia[2] == 1 and secuencia[-1] == -1:
        vela_racha = analisis.iloc[-2]
        vela_cambio = analisis.iloc[-1]
        punto_medio = (vela_racha['high'] + vela_racha['low']) / 2

        if vela_cambio['close'] < punto_medio:
            if estructura in ["alcista", "lateral"]:
                return "put"

    return None

def pro_signal(df):
    return get_signal(df)

import numpy as np
import pandas as pd

# ==================================================
# 🚀 ESTRATEGIA DE CONTINUIDAD DE TENDENCIA
# ✅ LÓGICA:
# 1. Detectar tendencia establecida (3+ velas del mismo color)
# 2. Confirmar que la siguiente vela mantiene la dirección
# 3. Aplicar filtros de fuerza para asegurar que la tendencia sigue
# 4. Solo operar A FAVOR de la dirección dominante
# ✅ REGLAS:
#    → 3+ VERDES + SIGUE VERDE = COMPRA (CALL)
#    → 3+ ROJAS + SIGUE ROJA = VENTA (PUT)
# ==================================================

def get_signal(df):
    """
    Devuelve señal solo si se confirma continuidad de la tendencia
    Devuelve: 'call' / 'put' / None
    """

    # 🛑 REQUISITO: Mínimo 8 velas para confirmar tendencia
    if len(df) < 8:
        return None

    # ======================================
    # 🔍 PASO 1: ANALIZAR ESTRUCTURA GENERAL
    # ======================================
    ultimas_8 = df.tail(8).copy()
    maximos = ultimas_8['high'].values
    minimos = ultimas_8['low'].values

    # Detectar tendencia general
    tendencia = "lateral"
    if maximos[-1] > maximos[-3] and minimos[-1] > minimos[-3]:
        tendencia = "alcista"
    elif maximos[-1] < maximos[-3] and minimos[-1] < minimos[-3]:
        tendencia = "bajista"

    # ======================================
    # 📊 PASO 2: DETECTAR SECUENCIA DE VELAS
    # ======================================
    ultimas_5 = df.tail(5).copy()
    ultimas_5['tipo'] = np.where(ultimas_5['close'] > ultimas_5['open'], 1, -1)
    secuencia = ultimas_5['tipo'].tolist()

    # ======================================
    # 🛡️ FILTROS DE FUERZA
    # ======================================
    df_analisis = df.tail(12).copy()
    df_analisis['rango'] = df_analisis['high'] - df_analisis['low']
    rango_promedio = df_analisis['rango'].mean()
    volumen_promedio = df_analisis['volume'].mean()

    vela_actual = ultimas_5.iloc[-1]
    vela_anterior = ultimas_5.iloc[-2]

    # 1. Tamaño suficiente de la vela actual
    tamaño_actual = vela_actual['high'] - vela_actual['low']
    if tamaño_actual < rango_promedio * 0.6:
        return None

    # 2. Volumen mayor o igual al promedio (confirma interés)
    if vela_actual['volume'] < volumen_promedio * 0.75:
        return None

    # ======================================
    # ✅ EVALUAR CONTINUIDAD
    # ======================================

    # 🟢 CASO 1: Continuidad alcista
    # 3 o más verdes seguidas, la última también es verde
    if secuencia[0] == 1 and secuencia[1] == 1 and secuencia[2] == 1 and secuencia[-1] == 1:
        # Confirmación: cierra por encima del cierre anterior
        if vela_actual['close'] > vela_anterior['close']:
            # Solo si la tendencia general es alcista o lateral
            if tendencia in ["alcista", "lateral"]:
                return "call"

    # 🔴 CASO 2: Continuidad bajista
    # 3 o más rojas seguidas, la última también es roja
    if secuencia[0] == -1 and secuencia[1] == -1 and secuencia[2] == -1 and secuencia[-1] == -1:
        # Confirmación: cierra por debajo del cierre anterior
        if vela_actual['close'] < vela_anterior['close']:
            # Solo si la tendencia general es bajista o lateral
            if tendencia in ["bajista", "lateral"]:
                return "put"

    # ❌ Si no hay continuidad clara: no operar
    return None

# ====================================================
# 🔄 Alias de compatibilidad
# ====================================================
def pro_signal(df):
    return get_signal(df)

import numpy as np
import pandas as pd

# ==================================================
# 🚀 ESTRATEGIA: RACHAS + LECTURA DE ESTRUCTURA
# ✅ LÓGICA:
# 1. DETECTAR ESTRUCTURA GENERAL DE CADA PAR
# 2. BUSCAR PATRÓN: 3+ velas iguales + 1 contraria
# 3. FILTROS DE FUERZA para evitar señales falsas
# ✅ REGLAS:
#    → 3+ VERDES + 1 ROJA = VENTA (PUT)
#    → 3+ ROJAS + 1 VERDE = COMPRA (CALL)
# ==================================================

def get_signal(df):
    """
    Analiza la secuencia de velas y la estructura del mercado
    Devuelve: 'call' / 'put' / None
    """

    # 🛑 REQUISITO: Necesitamos mínimo 8 velas para analizar estructura
    if len(df) < 8:
        return None

    # --------------------------
    # 🔍 PASO 1: LEER ESTRUCTURA DEL MERCADO
    # --------------------------
    ultimas_8 = df.tail(8).copy()
    maximos = ultimas_8['high'].values
    minimos = ultimas_8['low'].values

    estructura = "lateral"
    # Estructura alcista: máximos y mínimos crecientes
    if (maximos[-1] > maximos[-2] > maximos[-3]) and (minimos[-1] > minimos[-2] > minimos[-3]):
        estructura = "alcista"
    # Estructura bajista: máximos y mínimos decrecientes
    elif (maximos[-1] < maximos[-2] < maximos[-3]) and (minimos[-1] < minimos[-2] < minimos[-3]):
        estructura = "bajista"

    # --------------------------
    # 📊 PASO 2: ANALIZAR SECUENCIA DE VELAS
    # --------------------------
    ultimas_5 = df.tail(5).copy()
    # Clasificar velas: 1 = Verde, -1 = Roja
    ultimas_5['tipo'] = np.where(ultimas_5['close'] > ultimas_5['open'], 1, -1)
    secuencia = ultimas_5['tipo'].tolist()

    # --------------------------
    # 📏 FILTRO 1: TAMAÑO DE VELA
    # Evita velas sin fuerza (ruido)
    # --------------------------
    df_previo = df.tail(10).copy()
    df_previo['rango'] = df_previo['high'] - df_previo['low']
    rango_promedio = df_previo['rango'].mean()
    rango_minimo = rango_promedio * 0.6

    vela_cambio = ultimas_5.iloc[-1]
    tamaño_cambio = vela_cambio['high'] - vela_cambio['low']

    if tamaño_cambio < rango_minimo:
        return None

    # --------------------------
    # ✅ PASO 3: EVALUAR SEÑALES
    # --------------------------
    vela_racha = ultimas_5.iloc[-2]
    punto_medio_racha = (vela_racha['high'] + vela_racha['low']) / 2

    # 🔴 CASO 1: Racha alcista → Cambio a bajista
    if secuencia[0] == 1 and secuencia[1] == 1 and secuencia[2] == 1 and secuencia[-1] == -1:
        # Confirmación: cierra debajo del medio de la racha
        if vela_cambio['close'] < punto_medio_racha:
            # Solo válido si no va en contra de tendencia muy fuerte
            if estructura in ["alcista", "lateral"]:
                return "put"

    # 🟢 CASO 2: Racha bajista → Cambio a alcista
    if secuencia[0] == -1 and secuencia[1] == -1 and secuencia[2] == -1 and secuencia[-1] == 1:
        # Confirmación: cierra por encima del medio de la racha
        if vela_cambio['close'] > punto_medio_racha:
            # Solo válido si no va en contra de tendencia muy fuerte
            if estructura in ["bajista", "lateral"]:
                return "call"

    return None

# ====================================================
# 🔄 Alias de compatibilidad
# ====================================================
def pro_signal(df):
    return get_signal(df)

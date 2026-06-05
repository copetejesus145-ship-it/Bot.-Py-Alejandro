import numpy as np
import pandas as pd

# ==================================================
# 🚀 ESTRATEGIA SELECTIVA: RACHAS + ESTRUCTURA
# ✅ LÓGICA:
# 1. Detectar estructura del mercado por cada par
# 2. Buscar patrón: 3+ velas iguales + 1 contraria
# 3. Aplicar filtros estrictos para evitar señales falsas
# 4. Solo operar en oportunidades con confirmación
# ✅ REGLAS:
#    → 3+ VERDES + 1 ROJA = VENTA (PUT)
#    → 3+ ROJAS + 1 VERDE = COMPRA (CALL)
# ==================================================

def get_signal(df):
    """
    Analiza la secuencia de velas y devuelve señal solo si cumple todos los filtros
    Devuelve: 'call' / 'put' / None
    """

    # 🛑 REQUISITO: Mínimo 12 velas para analizar contexto completo
    if len(df) < 12:
        return None

    # ======================================
    # 🔍 PASO 1: LEER ESTRUCTURA DEL MERCADO
    # ======================================
    ultimas_10 = df.tail(10).copy()
    maximos = ultimas_10['high'].values
    minimos = ultimas_10['low'].values
    cierres = ultimas_10['close'].values

    estructura = "lateral"
    # Estructura alcista: máximos y mínimos crecientes
    if (maximos[-1] > maximos[-3]) and (minimos[-1] > minimos[-3]) and (cierres[-1] > cierres[-5]):
        estructura = "alcista"
    # Estructura bajista: máximos y mínimos decrecientes
    elif (maximos[-1] < maximos[-3]) and (minimos[-1] < minimos[-3]) and (cierres[-1] < cierres[-5]):
        estructura = "bajista"

    # ======================================
    # 📊 PASO 2: DETECTAR SECUENCIA DE VELAS
    # ======================================
    ultimas_5 = df.tail(5).copy()
    ultimas_5['tipo'] = np.where(ultimas_5['close'] > ultimas_5['open'], 1, -1)
    secuencia = ultimas_5['tipo'].tolist()

    # ======================================
    # 🛡️ FILTROS DE CALIDAD (evitan señales falsas)
    # ======================================
    df_analisis = df.tail(15).copy()
    df_analisis['rango'] = df_analisis['high'] - df_analisis['low']
    rango_promedio = df_analisis['rango'].mean()
    volumen_promedio = df_analisis['volume'].mean()

    vela_cambio = ultimas_5.iloc[-1]
    vela_racha = ultimas_5.iloc[-2]
    punto_medio_racha = (vela_racha['high'] + vela_racha['low']) / 2

    # 1. Tamaño mínimo de vela (evita velas sin fuerza)
    tamaño_cambio = vela_cambio['high'] - vela_cambio['low']
    if tamaño_cambio < rango_promedio * 0.7:
        return None

    # 2. Volumen suficiente (confirma interés en el movimiento)
    if vela_cambio['volume'] < volumen_promedio * 0.8:
        return None

    # ======================================
    # ✅ EVALUACIÓN DE OPORTUNIDADES
    # ======================================

    # 🔴 CASO 1: Racha alcista → Cambio a bajista
    if secuencia[0] == 1 and secuencia[1] == 1 and secuencia[2] == 1 and secuencia[-1] == -1:
        # Confirmación: cierra debajo del punto medio de la racha
        if vela_cambio['close'] < punto_medio_racha:
            # Solo válido si no va en contra de tendencia muy fuerte
            if estructura in ["alcista", "lateral"]:
                return "put"

    # 🟢 CASO 2: Racha bajista → Cambio a alcista
    if secuencia[0] == -1 and secuencia[1] == -1 and secuencia[2] == -1 and secuencia[-1] == 1:
        # Confirmación: cierra por encima del punto medio y cerca del máximo
        if vela_cambio['close'] > punto_medio_racha and vela_cambio['close'] > vela_racha['high'] * 0.98:
            # Solo válido si no va en contra de tendencia muy fuerte
            if estructura in ["bajista", "lateral"]:
                return "call"

    # ❌ No cumple condiciones: no operar
    return None

# ====================================================
# 🔄 Alias de compatibilidad
# ====================================================
def pro_signal(df):
    return get_signal(df)

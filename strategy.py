import numpy as np
import pandas as pd

# ==================================================
# 🚀 ESTRATEGIA SELECTIVA: SOLO OPORTUNIDADES CLARAS
# ✅ LÓGICA:
# 1. Leer estructura del mercado por cada par
# 2. Detectar patrón: 3+ velas seguidas + cambio de dirección
# 3. Aplicar filtros estrictos de fuerza y contexto
# 4. Solo operar si la probabilidad es favorable
# ==================================================

def get_signal(df):
    """
    Devuelve señal solo si se cumple todo el conjunto de condiciones
    """
    if len(df) < 12:
        return None

    # ======================================
    # 🔍 PASO 1: ANALIZAR ESTRUCTURA GENERAL
    # ======================================
    ultimas_10 = df.tail(10).copy()
    maximos = ultimas_10['high'].values
    minimos = ultimas_10['low'].values
    cierres = ultimas_10['close'].values

    # Definir estructura
    estructura = "lateral"
    fuerza_tendencia = 0

    if maximos[-1] > maximos[-3] and minimos[-1] > minimos[-3] and cierres[-1] > cierres[-5]:
        estructura = "alcista"
        fuerza_tendencia = 1
    elif maximos[-1] < maximos[-3] and minimos[-1] < minimos[-3] and cierres[-1] < cierres[-5]:
        estructura = "bajista"
        fuerza_tendencia = -1

    # ======================================
    # 📊 PASO 2: DETECTAR SECUENCIA DE VELAS
    # ======================================
    ultimas_5 = df.tail(5).copy()
    ultimas_5['tipo'] = np.where(ultimas_5['close'] > ultimas_5['open'], 1, -1)
    secuencia = ultimas_5['tipo'].tolist()

    # ======================================
    # 🛡️ FILTROS DE CALIDAD
    # ======================================
    df_analisis = df.tail(15).copy()
    df_analisis['rango'] = df_analisis['high'] - df_analisis['low']
    rango_promedio = df_analisis['rango'].mean()
    volumen_promedio = df_analisis['volume'].mean()

    vela_cambio = ultimas_5.iloc[-1]
    vela_racha = ultimas_5.iloc[-2]

    # 1. Tamaño suficiente
    if (vela_cambio['high'] - vela_cambio['low']) < rango_promedio * 0.7:
        return None

    # 2. Volumen mayor al promedio
    if vela_cambio['volume'] < volumen_promedio * 0.8:
        return None

    # 3. Cierre fuerte
    punto_medio = (vela_racha['high'] + vela_racha['low']) / 2

    # ======================================
    # ✅ EVALUAR OPORTUNIDADES
    # ======================================

    # CASO 1: Racha bajista → posible compra
    if secuencia[0] == -1 and secuencia[1] == -1 and secuencia[2] == -1 and secuencia[-1] == 1:
        # Confirmación de cambio real
        if vela_cambio['close'] > punto_medio and vela_cambio['close'] > vela_racha['high'] * 0.98:
            # Solo si no va en contra de tendencia muy fuerte
            if fuerza_tendencia >= -0.5:
                return "call"

    # CASO 2: Racha alcista → posible venta
    if secuencia[0] == 1 and secuencia[1] == 1 and secuencia[2] == 1 and secuencia[-1] == -1:
        # Confirmación de cambio real
        if vela_cambio['close'] < punto_medio and vela_cambio['close'] < vela_racha['low'] * 1.02:
            # Solo si no va en contra de tendencia muy fuerte
            if fuerza_tendencia <= 0.5:
                return "put"

    # ❌ Si no cumple todas las condiciones: NO OPERAR
    return None

# Compatibilidad
def pro_signal(df):
    return get_signal(df)

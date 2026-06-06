import numpy as np
import pandas as pd

# ==================================================
# 🚀 ESTRATEGIA: SOLO CONTINUIDAD EN TENDENCIA FUERTE
# ✅ LÓGICA ESTRICTA:
# 1. Requiere tendencia consolidada (máximos/mínimos crecientes/decrecientes)
# 2. Secuencia mínima: 4 velas seguidas del mismo color (no 3)
# 3. Filtros de fuerza: tamaño, volumen y velocidad del movimiento
# 4. DESCARTAR mercados laterales o sin fuerza
# ✅ REGLAS:
#    → 4+ VERDES + estructura alcista fuerte = COMPRA
#    → 4+ ROJAS + estructura bajista fuerte = VENTA
# ==================================================

def get_signal(df):
    """
    Devuelve señal SOLO si la tendencia es fuerte y consolidada
    Devuelve: 'call' / 'put' / None
    """

    # 🛑 REQUISITO: Más velas para confirmar estructura
    if len(df) < 15:
        return None

    # ======================================
    # 🔍 PASO 1: DETECTAR TENDENCIA FUERTE
    # ======================================
    ultimas_12 = df.tail(12).copy()
    maximos = ultimas_12['high'].values
    minimos = ultimas_12['low'].values
    cierres = ultimas_12['close'].values
    aperturas = ultimas_12['open'].values

    # Tendencia alcista fuerte: máximos y mínimos crecientes + cierres en zona alta
    tendencia_alcista_fuerte = (
        maximos[-1] > maximos[-2] > maximos[-3] > maximos[-4] and
        minimos[-1] > minimos[-2] > minimos[-3] > minimos[-4] and
        cierres[-1] > (maximos[-1] + minimos[-1]) / 2  # Cierra en la mitad superior
    )

    # Tendencia bajista fuerte: máximos y mínimos decrecientes + cierres en zona baja
    tendencia_bajista_fuerte = (
        maximos[-1] < maximos[-2] < maximos[-3] < maximos[-4] and
        minimos[-1] < minimos[-2] < minimos[-3] < minimos[-4] and
        cierres[-1] < (maximos[-1] + minimos[-1]) / 2  # Cierra en la mitad inferior
    )

    # Si no hay tendencia fuerte, no operar
    if not tendencia_alcista_fuerte and not tendencia_bajista_fuerte:
        return None

    # ======================================
    # 📊 PASO 2: SECUENCIA DE VELAS (más estricta)
    # ======================================
    ultimas_6 = df.tail(6).copy()
    ultimas_6['tipo'] = np.where(ultimas_6['close'] > ultimas_6['open'], 1, -1)
    secuencia = ultimas_6['tipo'].tolist()

    # ======================================
    # 🛡️ FILTROS DE FUERZA ADICIONALES
    # ======================================
    df_analisis = df.tail(15).copy()
    df_analisis['rango'] = df_analisis['high'] - df_analisis['low']
    rango_promedio = df_analisis['rango'].mean()
    volumen_promedio = df_analisis['volume'].mean()

    vela_actual = ultimas_6.iloc[-1]
    vela_anterior = ultimas_6.iloc[-2]

    # 1. Tamaño de vela: mínimo 80% del promedio
    tamaño_actual = vela_actual['high'] - vela_actual['low']
    if tamaño_actual < rango_promedio * 0.8:
        return None

    # 2. Volumen: mínimo 90% del promedio (confirma interés)
    if vela_actual['volume'] < volumen_promedio * 0.9:
        return None

    # 3. Cierre fuerte: más del 70% del cuerpo a favor de la tendencia
    cuerpo_vela = abs(vela_actual['close'] - vela_actual['open'])
    rango_vela = vela_actual['high'] - vela_actual['low']
    if cuerpo_vela < rango_vela * 0.7:
        return None

    # ======================================
    # ✅ EVALUACIÓN FINAL
    # ======================================

    # 🟢 CONTINUIDAD ALCISTA FUERTE
    if tendencia_alcista_fuerte and secuencia[-4] == 1 and secuencia[-3] == 1 and secuencia[-2] == 1 and secuencia[-1] == 1:
        if vela_actual['close'] > vela_anterior['close']:
            return "call"

    # 🔴 CONTINUIDAD BAJISTA FUERTE
    if tendencia_bajista_fuerte and secuencia[-4] == -1 and secuencia[-3] == -1 and secuencia[-2] == -1 and secuencia[-1] == -1:
        if vela_actual['close'] < vela_anterior['close']:
            return "put"

    # ❌ No cumple todas las condiciones estrictas
    return None

# ====================================================
# 🔄 Alias de compatibilidad
# ====================================================
def pro_signal(df):
    return get_signal(df)

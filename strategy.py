import numpy as np
import pandas as pd

# ==================================================
# 🚀 ESTRATEGIA: CONTINUIDAD - MEJOR ENTRADA
# ✅ LÓGICA:
# 1. Detecta tendencia general del mercado
# 2. Busca secuencia de 3 velas seguidas en la misma dirección
# 3. Calcula fuerza para elegir la mejor opción
# 4. Filtros equilibrados para operar con frecuencia y seguridad
# ==================================================

def get_signal(df):
    """
    Devuelve tupla (señal, fuerza) o None si no hay oportunidad
    Señales: 'call' / 'put'
    Fuerza: 0 a 100 puntos
    """

    if len(df) < 10:
        return None

    # ======================================
    # 🔍 ANÁLISIS DE TENDENCIA GENERAL
    # ======================================
    ultimas_8 = df.tail(8).copy()
    maximos = ultimas_8['high'].values
    minimos = ultimas_8['low'].values
    cierres = ultimas_8['close'].values

    tendencia = "lateral"
    fuerza_base = 0

    # Tendencia alcista
    if maximos[-1] > maximos[-3] and minimos[-1] > minimos[-3]:
        tendencia = "alcista"
        fuerza_base += 25

    # Tendencia bajista
    elif maximos[-1] < maximos[-3] and minimos[-1] < minimos[-3]:
        tendencia = "bajista"
        fuerza_base += 25

    # ======================================
    # 📊 SECUENCIA DE VELAS
    # ======================================
    ultimas_4 = df.tail(4).copy()
    ultimas_4['tipo'] = np.where(ultimas_4['close'] > ultimas_4['open'], 1, -1)
    secuencia = ultimas_4['tipo'].tolist()

    # ======================================
    # 🛡️ FILTROS DE FUERZA
    # ======================================
    df_analisis = df.tail(10).copy()
    df_analisis['rango'] = df_analisis['high'] - df_analisis['low']
    rango_promedio = df_analisis['rango'].mean()
    volumen_promedio = df_analisis['volume'].mean()

    v1 = ultimas_4.iloc[-1]
    v2 = ultimas_4.iloc[-2]
    v3 = ultimas_4.iloc[-3]

    # Tamaño mínimo de velas
    tamaño_prom = ((v1.high - v1.low) + (v2.high - v2.low) + (v3.high - v3.low)) / 3
    if tamaño_prom < rango_promedio * 0.5:
        return None
    fuerza_base += 15

    # Volumen aceptable
    volumen_prom = (v1.volume + v2.volume + v3.volume) / 3
    if volumen_prom < volumen_promedio * 0.6:
        return None
    fuerza_base += 10

    # Cuerpo de vela claro
    cuerpo_prom = (abs(v1.close - v1.open) + abs(v2.close - v2.open) + abs(v3.close - v3.open)) / 3
    if cuerpo_prom < tamaño_prom * 0.4:
        return None
    fuerza_base += 10

    # ======================================
    # ✅ DEFINIR SEÑAL
    # ======================================
    # Continuidad alcista
    if tendencia == "alcista" and secuencia[-3] == 1 and secuencia[-2] == 1 and secuencia[-1] == 1:
        fuerza_base += 25
        return ("call", min(fuerza_base, 100))

    # Continuidad bajista
    if tendencia == "bajista" and secuencia[-3] == -1 and secuencia[-2] == -1 and secuencia[-1] == -1:
        fuerza_base += 25
        return ("put", min(fuerza_base, 100))

    return None

# ====================================================
# 🔄 Alias de compatibilidad
# ====================================================
def pro_signal(df):
    res = get_signal(df)
    return res[0] if res else None

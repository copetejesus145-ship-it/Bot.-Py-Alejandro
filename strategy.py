import numpy as np
import pandas as pd

# ==================================================
# 🚀 ESTRATEGIA: CONTINUIDAD FUERTE - VERSIÓN EQUILIBRADA
# ✅ CAMBIOS CLAVE:
# - De 4 a 3 velas seguidas (más natural en mercado)
# - Filtros de volumen/tamaño menos estrictos
# - Sigue priorizando tendencia fuerte
# ==================================================

def get_signal(df):
    """
    Devuelve (señal, fuerza) o None
    """
    if len(df) < 12:
        return None

    # ======================================
    # 🔍 ANÁLISIS DE TENDENCIA
    # ======================================
    ultimas_10 = df.tail(10).copy()
    maximos = ultimas_10['high'].values
    minimos = ultimas_10['low'].values
    cierres = ultimas_10['close'].values

    fuerza = 0

    # Tendencia alcista fuerte
    tendencia_alcista = (
        maximos[-1] > maximos[-3] and
        minimos[-1] > minimos[-3] and
        cierres[-1] > cierres[-4]
    )

    # Tendencia bajista fuerte
    tendencia_bajista = (
        maximos[-1] < maximos[-3] and
        minimos[-1] < minimos[-3] and
        cierres[-1] < cierres[-4]
    )

    if not tendencia_alcista and not tendencia_bajista:
        return None

    fuerza += 30

    # ======================================
    # 📊 SECUENCIA DE VELAS (3 seguidas ahora)
    # ======================================
    ultimas_5 = df.tail(5).copy()
    ultimas_5['tipo'] = np.where(ultimas_5['close'] > ultimas_5['open'], 1, -1)
    secuencia = ultimas_5['tipo'].tolist()

    # ======================================
    # 🛡️ FILTROS MÁS FLEXIBLES
    # ======================================
    df_analisis = df.tail(12).copy()
    df_analisis['rango'] = df_analisis['high'] - df_analisis['low']
    rango_promedio = df_analisis['rango'].mean()
    volumen_promedio = df_analisis['volume'].mean()

    v1 = ultimas_5.iloc[-1]
    v2 = ultimas_5.iloc[-2]
    v3 = ultimas_5.iloc[-3]

    # Tamaño de vela: mínimo 60% del promedio (antes 80%)
    tamaño_prom = ((v1.high - v1.low)+(v2.high - v2.low)+(v3.high - v3.low)) / 3
    if tamaño_prom < rango_promedio * 0.6:
        return None
    fuerza += 20

    # Volumen: mínimo 70% del promedio (antes 90%)
    vol_prom = (v1.volume + v2.volume + v3.volume) / 3
    if vol_prom < volumen_promedio * 0.7:
        return None
    fuerza += 15

    # Cuerpo: mínimo 50% del rango (antes 70%)
    cuerpo_prom = (abs(v1.close - v1.open)+abs(v2.close - v2.open)+abs(v3.close - v3.open)) / 3
    if cuerpo_prom < tamaño_prom * 0.5:
        return None
    fuerza += 15

    # ======================================
    # ✅ DEFINIR SEÑAL
    # ======================================
    if tendencia_alcista and secuencia[-3] == 1 and secuencia[-2] == 1 and secuencia[-1] == 1:
        fuerza += 20
        return ("call", min(fuerza, 100))

    if tendencia_bajista and secuencia[-3] == -1 and secuencia[-2] == -1 and secuencia[-1] == -1:
        fuerza += 20
        return ("put", min(fuerza, 100))

    return None

# ====================================================
# 🔄 Alias de compatibilidad
# ====================================================
def pro_signal(df):
    res = get_signal(df)
    return res[0] if res else None

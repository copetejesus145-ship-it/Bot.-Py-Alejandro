import numpy as np
import pandas as pd

# ==================================================
# 🚀 ESTRATEGIA: SOLO A FAVOR DE LA TENDENCIA
# ✅ LÓGICA NUEVA:
# 1. Definir tendencia principal en marco de 5 minutos
# 2. Buscar entradas solo en la misma dirección
# 3. Confirmar continuidad y fuerza en 1 minuto
# 4. NUNCA operar en contra de la tendencia
# ==================================================

def get_trend_signal(df_tendencia, df_entrada):
    """
    Devuelve (señal, fuerza, direccion) o None
    Solo genera señal si coincide con la tendencia principal
    """

    if len(df_tendencia) < 15 or len(df_entrada) < 10:
        return None

    # ======================================
    # 🔍 PASO 1: DEFINIR TENDENCIA PRINCIPAL
    # ======================================
    ultimas_tendencia = df_tendencia.tail(12).copy()
    maximos = ultimas_tendencia['high'].values
    minimos = ultimas_tendencia['low'].values
    cierres = ultimas_tendencia['close'].values

    tendencia = "lateral"
    fuerza_base = 0

    # Tendencia alcista: máximos y mínimos crecientes
    if (maximos[-1] > maximos[-3] > maximos[-6] and
        minimos[-1] > minimos[-3] > minimos[-6] and
        cierres[-1] > cierres[-6]):
        tendencia = "alcista"
        fuerza_base += 35

    # Tendencia bajista: máximos y mínimos decrecientes
    elif (maximos[-1] < maximos[-3] < maximos[-6] and
          minimos[-1] < minimos[-3] < minimos[-6] and
          cierres[-1] < cierres[-6]):
        tendencia = "bajista"
        fuerza_base += 35

    # Si no hay tendencia clara: no operar
    if tendencia == "lateral":
        return None

    # ======================================
    # 📊 PASO 2: BUSCAR ENTRADA A FAVOR
    # ======================================
    ultimas_entrada = df_entrada.tail(6).copy()
    ultimas_entrada['tipo'] = np.where(ultimas_entrada['close'] > ultimas_entrada['open'], 1, -1)
    secuencia = ultimas_entrada['tipo'].tolist()

    # ======================================
    # 🛡️ FILTROS DE CONFIRMACIÓN
    # ======================================
    df_analisis = df_entrada.tail(10).copy()
    df_analisis['rango'] = df_analisis['high'] - df_analisis['low']
    rango_prom = df_analisis['rango'].mean()
    volumen_prom = df_analisis['volume'].mean()

    v1 = ultimas_entrada.iloc[-1]
    v2 = ultimas_entrada.iloc[-2]
    v3 = ultimas_entrada.iloc[-3]

    # Tamaño de vela suficiente
    tamaño_prom = ((v1.high - v1.low) + (v2.high - v2.low) + (v3.high - v3.low)) / 3
    if tamaño_prom < rango_prom * 0.5:
        return None
    fuerza_base += 15

    # Volumen de confirmación
    vol_prom = (v1.volume + v2.volume + v3.volume) / 3
    if vol_prom < volumen_prom * 0.6:
        return None
    fuerza_base += 10

    # Cuerpo claro
    cuerpo_prom = (abs(v1.close - v1.open) + abs(v2.close - v2.open) + abs(v3.close - v3.open)) / 3
    if cuerpo_prom < tamaño_prom * 0.4:
        return None
    fuerza_base += 10

    # ======================================
    # ✅ DEFINIR SEÑAL FINAL
    # ======================================
    if tendencia == "alcista":
        # Buscar continuidad alcista
        if secuencia[-3] == 1 and secuencia[-2] == 1 and secuencia[-1] == 1:
            fuerza_base += 20
            return ("call", min(fuerza_base, 100), "alcista")

    elif tendencia == "bajista":
        # Buscar continuidad bajista
        if secuencia[-3] == -1 and secuencia[-2] == -1 and secuencia[-1] == -1:
            fuerza_base += 20
            return ("put", min(fuerza_base, 100), "bajista")

    return None

# ====================================================
# 🔄 Alias de compatibilidad
# ====================================================
def pro_signal(df):
    return None

import numpy as np
import pandas as pd

# ==================================================
# 🚀 ESTRATEGIA EXACTA - PATRÓN DE LA IMAGEN
# ✅ PATRÓN: 3 VERDES + 1 ROJA = VENTA
# ✅ PATRÓN: 3 ROJAS + 1 VERDE = COMPRA
# ✅ SOLO ESTA LÓGICA, SIN OTROS INDICADORES
# ✅ ACTIVO: EURUSD OTC | 1 MINUTO
# ==================================================

# ============================================
# 📊 DETECCIÓN DE PATRÓN DE VELAS
# ============================================

def get_signal(df):
    """
    FUNCIÓN PRINCIPAL:
    Analiza las últimas 4 velas cerradas.
    Si cumple el patrón → Devuelve señal.
    Si no cumple → No opera.
    """
    # Necesitamos al menos 4 velas para analizar el patrón
    if len(df) < 4:
        return None

    # 📥 TOMAMOS LAS ÚLTIMAS 4 VELAS CERRADAS
    # (El patrón es de 4 velas: 3 iguales + 1 contraria)
    ultimas_4 = df.tail(4).copy()

    # 🟩 CLASIFICAR VELAS:
    #  1 = VERDE (Alcista: Cierre > Apertura)
    # -1 = ROJA (Bajista: Cierre < Apertura)
    ultimas_4['tipo'] = np.where(ultimas_4['close'] > ultimas_4['open'], 1, -1)

    # Convertimos la secuencia a lista para leerla fácil
    secuencia = ultimas_4['tipo'].tolist()

    # ============================================
    # 🟢 PATRÓN 1: 3 VERDES + 1 ROJA → VENDER (PUT)
    # Secuencia: [1, 1, 1, -1]
    # ============================================
    if secuencia == [1, 1, 1, -1]:
        return "put"

    # ============================================
    # 🔴 PATRÓN 2: 3 ROJAS + 1 VERDE → COMPRAR (CALL)
    # Secuencia: [-1, -1, -1, 1]
    # ============================================
    if secuencia == [-1, -1, -1, 1]:
        return "call"

    # ❌ SI NO CUMPLE NINGÚN PATRÓN: NO OPERAR
    return None


# ============================================
# 🔄 COMPATIBILIDAD CON TU BOT
# ============================================

def pro_signal(df):
    """Alias para mantener compatibilidad con tu código principal"""
    return get_signal(df)

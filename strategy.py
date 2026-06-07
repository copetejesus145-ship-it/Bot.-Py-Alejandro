import numpy as np
import pandas as pd

# ==================================================
# 🚀 ESTRATEGIA EXACTA BASADA EN TUS GRÁFICOS
# ✅ LÓGICA DETECTADA:
#    1. RACHAS LARGAS: 3 o más velas seguidas del mismo color
#    2. CAMBIO DE ESTRUCTURA: Aparece la primera vela de color contrario
#    3. ENTRADA: Operar en dirección a la nueva vela (REVERSIÓN)
# ✅ REGLA DE ORO:
#    → 3 VERDES (o más) + 1 ROJA = VENDER (PUT)
#    → 3 ROJAS (o más) + 1 VERDE = COMPRAR (CALL)
# ✅ SOLO ESTE PATRÓN, SIN INDICADORES EXTERNOS
# ==================================================

def get_signal(df):
    """
    FUNCIÓN PRINCIPAL DE ANÁLISIS
    Recibe el DataFrame con todas las velas descargadas
    Devuelve: 'call' / 'put' / None (si no cumple la regla)
    """

    # 🛑 REQUISITO MÍNIMO: Necesitamos al menos 4 velas para analizar
    # (3 de la racha + 1 del cambio)
    if len(df) < 4:
        return None

    # 📥 SELECCIONAMOS LAS ÚLTIMAS 5 VELAS
    # Tomamos 5 para cubrir casos donde la racha sea de 4 o 5 velas
    ultimas_velas = df.tail(5).copy()

    # 🟩 CLASIFICACIÓN DE VELAS:
    # Convertimos cada vela en un número para leer la secuencia fácil:
    #  1 = VERDE  → Alcista (Cierre > Apertura)
    # -1 = ROJA   → Bajista (Cierre < Apertura)
    ultimas_velas['tipo'] = np.where(ultimas_velas['close'] > ultimas_velas['open'], 1, -1)

    # Convertimos la columna a lista para analizar el orden
    secuencia = ultimas_velas['tipo'].tolist()

    # ============================================
    # 🔴 CASO 1: RACHA DE SUBIDA → CAMBIO A BAJADA
    # ============================================
    # Condición: Las 3 primeras velas son VERDES, la ÚLTIMA es ROJA
    # Ejemplos válidos: [1,1,1,-1], [1,1,1,1,-1], [1,1,1,-1,1]
    if secuencia[0] == 1 and secuencia[1] == 1 and secuencia[2] == 1 and secuencia[-1] == -1:
        return "put"  # 📉 SEÑAL DE VENTA: La tendencia se invierte a la baja

    # ============================================
    # 🟢 CASO 2: RACHA DE BAJADA → CAMBIO A SUBIDA
    # ============================================
    # Condición: Las 3 primeras velas son ROJAS, la ÚLTIMA es VERDE
    # Ejemplos válidos: [-1,-1,-1,1], [-1,-1,-1,-1,1], [-1,-1,-1,1,-1]
    if secuencia[0] == -1 and secuencia[1] == -1 and secuencia[2] == -1 and secuencia[-1] == 1:
        return "call" # 📈 SEÑAL DE COMPRA: La tendencia se invierte al alza

    # ❌ SI NO CUMPLE NINGUNA DE LAS REGLAS: NO OPERAR
    return None


# ============================================
# 🔄 FUNCIÓN DE COMPATIBILIDAD
# Mantiene el nombre que usa tu bot principal
# ============================================
def pro_signal(df):
    """Alias de seguridad para asegurar compatibilidad total"""
    return get_signal(df)

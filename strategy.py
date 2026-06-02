import numpy as np
import pandas as pd

# ==================================================
# 🚀 ESTRATEGIA EXACTA DE TUS IMÁGENES
# ✅ LO QUE SE VE EN GRÁFICOS:
#    - RACHAS LARGAS: 3, 4 o más velas iguales seguidas
#    - CAMBIO: Aparece la primera vela de color contrario
# ✅ LÓGICA DE ENTRADA: REVERSIÓN
#    → Si 3+ VERDES + 1 ROJA = VENDER (PUT)
#    → Si 3+ ROJAS + 1 VERDE = COMPRAR (CALL)
# ✅ SOLO ESTA LÓGICA, SIN OTROS INDICADORES
# ==================================================

def get_signal(df):
    """
    FUNCIÓN PRINCIPAL DE ANÁLISIS:
    Recibe el DataFrame con las velas.
    Devuelve: 'call' / 'put' / None
    """
    # Necesitamos mínimo 4 velas para detectar la racha + cambio
    if len(df) < 4:
        return None

    # 📥 TOMAMOS LAS ÚLTIMAS 5 VELAS (Suficiente para ver la estructura)
    ultimas = df.tail(5).copy()

    # 🟩 CLASIFICAR VELAS:
    #  1 = VERDE (Alcista: Cierre > Apertura)
    # -1 = ROJA (Bajista: Cierre < Apertura)
    ultimas['tipo'] = np.where(ultimas['close'] > ultimas['open'], 1, -1)

    # Convertimos a lista para leer la secuencia fácilmente
    secuencia = ultimas['tipo'].tolist()

    # ============================================
    # 🔴 CASO 1: RACHA DE SUBIDA → CAMBIO A BAJADA
    # Estructura vista: [1, 1, 1, -1, ...] o [1,1,1,1,-1]
    # Regla: Las 3 primeras son VERDES, la ÚLTIMA es ROJA
    # ============================================
    if secuencia[0] == 1 and secuencia[1] == 1 and secuencia[2] == 1 and secuencia[-1] == -1:
        return "put" # 📉 VENDER: La tendencia cambió a la baja

    # ============================================
    # 🟢 CASO 2: RACHA DE BAJADA → CAMBIO A SUBIDA
    # Estructura vista: [-1, -1, -1, 1, ...] o [-1,-1,-1,-1,1]
    # Regla: Las 3 primeras son ROJAS, la ÚLTIMA es VERDE
    # ============================================
    if secuencia[0] == -1 and secuencia[1] == -1 and secuencia[2] == -1 and secuencia[-1] == 1:
        return "call" # 📈 COMPRAR: La tendencia cambió al alza

    # ❌ SI NO CUMPLE EL PATRÓN: NO OPERAR
    return None


# ============================================
# 🔄 COMPATIBILIDAD CON EL BOT
# ============================================
def pro_signal(df):
    """Alias para asegurar compatibilidad con el archivo principal"""
    return get_signal(df)

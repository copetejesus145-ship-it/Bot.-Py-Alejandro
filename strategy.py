import numpy as np
import pandas as pd

# ==================================================
# 🚀 ESTRATEGIA: REVERSIÓN EN SOPORTE / RESISTENCIA
# ✅ Optimizada para encontrar más señales
# ✅ Reglas claras pero flexibles
# ✅ Sin errores
# ==================================================

def get_reversal_signal(df, tolerancia=0.0012, ventana=6):
    if len(df) < ventana + 2:
        return None

    df = df.copy()

    # --------------------------
    # DETECTAR NIVELES CLAVE
    # --------------------------
    # Soportes (mínimos recientes)
    df['minimo'] = df['low'].rolling(window=ventana, center=False).min()
    soportes = df['minimo'].dropna().unique()
    soportes = sorted([s for s in soportes if s > 0])

    # Resistencias (máximos recientes)
    df['maximo'] = df['high'].rolling(window=ventana, center=False).max()
    resistencias = df['maximo'].dropna().unique()
    resistencias = sorted([r for r in resistencias if r > 0])

    # --------------------------
    # VALORES ACTUALES
    # --------------------------
    try:
        cierre = float(df['close'].iloc[-1])
        apertura = float(df['open'].iloc[-1])
        alto = float(df['high'].iloc[-1])
        bajo = float(df['low'].iloc[-1])
        
        # Tendencia de las últimas 2 velas
        cierre_anterior = float(df['close'].iloc[-2])
        tendencia_anterior = cierre_anterior - float(df['close'].iloc[-3]) if len(df)>=3 else 0

    except Exception:
        return None

    senal = None
    fuerza = 0
    tipo_nivel = ""

    # --------------------------
    # COMPRA EN SOPORTE
    # --------------------------
    for soporte in soportes:
        if abs(cierre - soporte) <= tolerancia:
            # Veníamos bajando o lateral
            if tendencia_anterior <= 0:
                # Vela muestra cambio
                if cierre > apertura:
                    senal = "call"
                    tipo_nivel = "Soporte"
                    fuerza = 40
                    if bajo >= soporte - tolerancia:
                        fuerza += 15
                    if (cierre - apertura) > tolerancia * 0.3:
                        fuerza += 15
                    break

    # --------------------------
    # VENTA EN RESISTENCIA
    # --------------------------
    if senal is None:
        for resistencia in resistencias:
            if abs(cierre - resistencia) <= tolerancia:
                # Veníamos subiendo o lateral
                if tendencia_anterior >= 0:
                    # Vela muestra cambio
                    if cierre < apertura:
                        senal = "put"
                        tipo_nivel = "Resistencia"
                        fuerza = 40
                        if alto <= resistencia + tolerancia:
                            fuerza += 15
                        if (apertura - cierre) > tolerancia * 0.3:
                            fuerza += 15
                        break

    if senal is None:
        return None

    return (senal, min(fuerza, 100), tipo_nivel)

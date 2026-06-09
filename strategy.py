import numpy as np
import pandas as pd

# ==================================================
# 🚀 ESTRATEGIA: REVERSIÓN EN SOPORTE / RESISTENCIA
# ✅ Opera SOLO si el precio cierra JUSTO en el nivel
# ✅ Entra en reversión
# ✅ SIN ERRORES DE SINTAXIS
# ==================================================

def get_reversal_signal(df, tolerancia=0.0003):
    if len(df) < 30:
        return None

    df = df.copy()

    # --------------------------
    # DETECTAR NIVELES CLAVE
    # --------------------------
    # Soportes (mínimos recientes)
    df['minimo'] = df['low'].rolling(window=10, center=True).min()
    soportes = df['minimo'].dropna().unique()
    soportes = sorted([s for s in soportes if s > 0])

    # Resistencias (máximos recientes)
    df['maximo'] = df['high'].rolling(window=10, center=True).max()
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
        
        # Tendencia anterior
        cierre_anterior = float(df['close'].iloc[-2])
        cierre_anterior2 = float(df['close'].iloc[-3])
        tendencia_anterior = cierre_anterior - cierre_anterior2

    except Exception:
        return None

    senal = None
    fuerza = 0
    tipo_nivel = ""

    # --------------------------
    # CONDICIÓN 1: CIERRE EN SOPORTE → COMPRA
    # --------------------------
    for soporte in soportes:
        if abs(cierre - soporte) <= tolerancia:
            # Venía bajando
            if tendencia_anterior < 0:
                # Vela de reversión alcista
                if cierre > apertura and (cierre - apertura) > tolerancia * 1.5:
                    senal = "call"
                    tipo_nivel = "Soporte"
                    fuerza = 70
                    # Confirmaciones extra
                    if bajo >= soporte - tolerancia:
                        fuerza += 10
                    if volumen := float(df['volume'].iloc[-1]) > float(df['volume'].iloc[-5:-1].mean()) * 0.8:
                        fuerza += 10
                    break

    # --------------------------
    # CONDICIÓN 2: CIERRE EN RESISTENCIA → VENTA
    # --------------------------
    if senal is None:
        for resistencia in resistencias:
            if abs(cierre - resistencia) <= tolerancia:
                # Venía subiendo
                if tendencia_anterior > 0:
                    # Vela de reversión bajista
                    if cierre < apertura and (apertura - cierre) > tolerancia * 1.5:
                        senal = "put"
                        tipo_nivel = "Resistencia"
                        fuerza = 70
                        # Confirmaciones extra
                        if alto <= resistencia + tolerancia:
                            fuerza += 10
                        if volumen := float(df['volume'].iloc[-1]) > float(df['volume'].iloc[-5:-1].mean()) * 0.8:
                            fuerza += 10
                        break

    if senal is None:
        return None

    return (senal, min(fuerza, 100), tipo_nivel)

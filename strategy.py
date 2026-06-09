import numpy as np
import pandas as pd

# ==================================================
# 🚀 ESTRATEGIA DE MOMENTUM PURA
# ✅ Busca movimientos fuertes y continuos
# ✅ Usa EMA, ADX, y confirmación de velas
# ==================================================

def get_momentum_signal(df):
    # Necesitamos al menos 30 velas para el cálculo del ADX
    if len(df) < 30:
        return None

    df = df.copy()

    # --------------------------
    # CÁLCULO DE INDICADORES
    # --------------------------
    # Medias Móviles Exponenciales para detectar cruces y tendencia
    df['ema5'] = df['close'].ewm(span=5, adjust=False).mean()
    df['ema10'] = df['close'].ewm(span=10, adjust=False).mean()
    df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()

    # Cálculo de ADX para la fuerza de la tendencia
    df['tr'] = np.maximum(
        df['high'] - df['low'],
        np.maximum(
            abs(df['high'] - df['close'].shift(1)),
            abs(df['low'] - df['close'].shift(1))
        )
    )
    df['dm_plus'] = np.where(
        (df['high'] - df['high'].shift(1)) > (df['low'].shift(1) - df['low']),
        np.maximum(df['high'] - df['high'].shift(1), 0.0),
        0.0
    )
    df['dm_minus'] = np.where(
        (df['low'].shift(1) - df['low']) > (df['high'] - df['high'].shift(1)),
        np.maximum(df['low'].shift(1) - df['low'], 0.0),
        0.0
    )

    tr14 = df['tr'].rolling(14).sum().replace(0, 0.001)
    dmp14 = df['dm_plus'].rolling(14).sum()
    dmm14 = df['dm_minus'].rolling(14).sum()

    di_plus = 100.0 * dmp14 / tr14
    di_minus = 100.0 * dmm14 / tr14
    di_sum = (di_plus + di_minus).replace(0, 0.001)
    dx = 100.0 * abs(di_plus - di_minus) / di_sum
    df['adx'] = dx.rolling(14).mean()

    # --------------------------
    # EXTRACCIÓN SEGURA DE VALORES
    # --------------------------
    try:
        ema5_1 = float(df['ema5'].iloc[-1])
        ema10_1 = float(df['ema10'].iloc[-1])
        ema20_1 = float(df['ema20'].iloc[-1])

        c1 = float(df['close'].iloc[-1])
        c2 = float(df['close'].iloc[-2])
        c3 = float(df['close'].iloc[-3])
        
        o1 = float(df['open'].iloc[-1])
        o2 = float

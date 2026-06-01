import numpy as np
import pandas as pd

# ==================================================
# 🚀 STRATEGY BINARIAS OTC 1MIN - VERSION PRO
# ✅ Configurado para: OTC | 1min Vela | 1min Expiración
# ✅ Indicadores: Bollinger Bands | ZigZag | Fractales
# ✅ Lógica Corregida + Optimizada
# ==================================================

# ============================================
# 📊 INDICADORES TÉCNICOS
# ============================================

def bollinger_bands(df, window=20, std_dev=2):
    """
    Calcula Bandas de Bollinger
    Ventana 20 / Desviación 2 -> Estándar y óptimo para 1min OTC
    """
    df = df.copy()
    df['sma'] = df['close'].rolling(window=window).mean()
    df['upper_band'] = df['sma'] + (df['close'].rolling(window=window).std() * std_dev)
    df['lower_band'] = df['sma'] - (df['close'].rolling(window=window).std() * std_dev)
    return df


def zigzag_detection(df, pips_threshold=0.0005):
    """
    Detección de giros ZigZag adaptado a EUR/USD OTC
    pips_threshold=0.0005 -> Sensibilidad alta para 1 minuto
    """
    df = df.copy()
    df['zigzag'] = 0
    last_swing_high = None
    last_swing_low = None

    for i in range(3, len(df)-2):
        # DETECTAR PICO ALTO (SEÑAL BAJISTA)
        if (df['high'].iloc[i] > df['high'].iloc[i-1] and
            df['high'].iloc[i] > df['high'].iloc[i-2] and
            df['high'].iloc[i] > df['high'].iloc[i+1] and
            df['high'].iloc[i] > df['high'].iloc[i+2]):

            if last_swing_high is None or (df['high'].iloc[i] - last_swing_high) > pips_threshold:
                df.loc[df.index[i], 'zigzag'] = 1  # 1 = Pico Alto (Venta/PUT)
                last_swing_high = df['high'].iloc[i]

        # DETECTAR VALLE BAJO (SEÑAL ALCISTA)
        if (df['low'].iloc[i] < df['low'].iloc[i-1] and
            df['low'].iloc[i] < df['low'].iloc[i-2] and
            df['low'].iloc[i] < df['low'].iloc[i+1] and
            df['low'].iloc[i] < df['low'].iloc[i+2]):

            if last_swing_low is None or (last_swing_low - df['low'].iloc[i]) > pips_threshold:
                df.loc[df.index[i], 'zigzag'] = -1 # -1 = Valle Bajo (Compra/CALL)
                last_swing_low = df['low'].iloc[i]

    return df


def fractal_signal(df):
    """
    Fractales de Bill Williams - Configuración Estándar (5 velas)
    Fractal Arriba = Señal PUT | Fractal Abajo = Señal CALL
    """
    df = df.copy()
    df['fractal_up'] = False
    df['fractal_down'] = False

    if len(df) < 5:
        return df

    for i in range(2, len(df)-2):
        # FRACTAL SUPERIOR (PUT) -> Máximo central es el más alto
        if (df['high'].iloc[i] > df['high'].iloc[i-2] and
            df['high'].iloc[i] > df['high'].iloc[i-1] and
            df['high'].iloc[i] > df['high'].iloc[i+1] and
            df['high'].iloc[i] > df['high'].iloc[i+2]):
            df.loc[df.index[i], 'fractal_up'] = True

        # FRACTAL INFERIOR (CALL) -> Mínimo central es el más bajo
        if (df['low'].iloc[i] < df['low'].iloc[i-2] and
            df['low'].iloc[i] < df['low'].iloc[i-1] and
            df['low'].iloc[i] < df['low'].iloc[i+1] and
            df['low'].iloc[i] < df['low'].iloc[i+2]):
            df.loc[df.index[i], 'fractal_down'] = True

    return df

# ============================================
# 📈 ANÁLISIS DE PRECIO - PRICE ACTION
# ============================================

def near_support_resistance(df):
    """
    ZONAS DE SOPORTE / RESISTENCIA
    ✅ Ventana: 20 velas (rápido para 1min)
    ✅ Umbral: 1.5% -> Zona MUY PRECISA (no ruido)
    RETORNA: False / 'soporte' / 'resistencia'
    """
    last_candle = df.iloc[-1]
    close_price = last_candle['close']

    # Máximos/Mínimos de las últimas 20 velas
    resistance_level = df['high'].rolling(20).max().iloc[-2]
    support_level = df['low'].rolling(20).min().iloc[-2]
    price_range = resistance_level - support_level

    if price_range == 0:
        return False

    # Zona estrecha: 1.5% del rango total
    threshold = price_range * 0.015

    if abs(close_price - resistance_level) < threshold:
        return "resistencia"
    if abs(close_price - support_level) < threshold:
        return "soporte"

    return False


def strong_trend_movement(df):
    """
    DETECTA FUERZA DE TENDENCIA
    Movimiento > 18% del rango = Tendencia clara y fuerte
    """
    price_move = abs(df['close'].iloc[-1] - df['close'].iloc[-7]) # Últimos 6 minutos
    total_range = df['high'].tail(12).max() - df['low'].tail(12).min()

    if total_range == 0:
        return False

    return price_move > total_range * 0.18


def rejection_candle_analysis(candle, direction):
    """
    VELAS DE RECHAZO (MECHAS LARGAS)
    ✅ Mecha > 1.5x tamaño del cuerpo = Rechazo fuerte
    CALL = Rechazo abajo | PUT = Rechazo arriba
    """
    body_size = abs(candle['close'] - candle['open'])
    candle_total_range = candle['high'] - candle['low']

    if body_size == 0 or candle_total_range == 0:
        return False

    wick_upper = candle['high'] - max(candle['open'], candle['close'])
    wick_lower = min(candle['open'], candle['close']) - candle['low']

    # LOGICA CORRECTA
    if direction == "call" and wick_lower > body_size * 1.5:
        return True
    if direction == "put" and wick_upper > body_size * 1.5:
        return True

    return False


def is_strong_candle(candle):
    """Vela fuerte: Cuerpo > 65% del rango total"""
    body = abs(candle['close'] - candle['open'])
    rng = candle['high'] - candle['low']
    return rng > 0 and (body / rng) > 0.65


def price_continuation(df, direction):
    """
    CONFIRMACIÓN DE CONTINUIDAD
    ✅ La vela actual confirma la dirección de la anterior
    """
    last = df.iloc[-1]
    prev = df.iloc[-2]

    if direction == "call":
        return last['close'] > last['open'] and last['low'] > prev['low'] and is_strong_candle(last)
    if direction == "put":
        return last['close'] < last['open'] and last['high'] < prev['high'] and is_strong_candle(last)

    return False


def get_trend_direction(df):
    """
    🧠 LOGICA PRINCIPAL DE DIRECCIÓN - CORREGIDA 100%
    ✅ ROMPE ARRIBA = FUERZA COMPRADORA -> CALL
    ✅ ROMPE ABAJO = FUERZA VENDEDORA -> PUT
    """
    last = df.iloc[-1]
    prev = df.iloc[-2]
    prev2 = df.iloc[-3]

    # 🟢 SEÑAL CALL: Precio rompe hacia ARRIBA
    if last['close'] > prev['high'] and prev['high'] > prev2['high']:
        return "call"

    # 🔴 SEÑAL PUT: Precio rompe hacia ABAJO
    if last['close'] < prev['low'] and prev['low'] < prev2['low']:
        return "put"

    return None

# ============================================
# ✅ FUNCIÓN PRINCIPAL - SEÑAL FINAL
# ============================================

def get_signal(df):
    """
    FUNCIÓN LLAMADA POR EL BOT
    RETORNA: 'call' / 'put' / None
    """

    # 1. Verificar datos suficientes (80 velas = 1h 20min)
    if len(df) < 80:
        return None

    # 2. Calcular TODOS los indicadores
    df = bollinger_bands(df)
    df = zigzag_detection(df)
    df = fractal_signal(df)

    # 3. Obtener dirección del precio
    direction = get_trend_direction(df)
    if direction is None:
        return None

    # 4. SOLO operar si estamos en ZONA CLAVE (Soporte/Resistencia)
    zone = near_support_resistance(df)
    if not zone:
        return None

    # 5. Confirmar que hay FUERZA DE TENDENCIA
    if not strong_trend_movement(df):
        return None

    # 6. Confirmar CONTINUIDAD del movimiento
    if not price_continuation(df, direction):
        return None

    # 7. 🎯 CONFIRMACIONES FINALES (4 FILTROS CLAVE)
    last_candle = df.iloc[-1]

    # FILTRO 1: Bandas de Bollinger
    bollinger_ok = False
    if direction == "call" and last_candle['low'] <= last_candle['lower_band'] * 1.002:
        bollinger_ok = True
    if direction == "put" and last_candle['high'] >= last_candle['upper_band'] * 0.998:
        bollinger_ok = True

    # FILTRO 2: ZigZag
    zigzag_ok = False
    if direction == "call" and df['zigzag'].iloc[-5:-1].isin([-1]).any():
        zigzag_ok = True
    if direction == "put" and df['zigzag'].iloc[-5:-1].isin([1]).any():
        zigzag_ok = True

    # FILTRO 3: Fractales
    fractal_ok = False
    if direction == "call" and df['fractal_down'].iloc[-5:-1].any():
        fractal_ok = True
    if direction == "put" and df['fractal_up'].iloc[-5:-1].any():
        fractal_ok = True

    # FILTRO 4: Rechazo de vela
    rejection_ok = rejection_candle_analysis(last_candle, direction)

    # 8. ✅ REGLA DE ORO: Mínimo 3 de 4 filtros deben coincidir
    total_confirmations = sum([bollinger_ok, zigzag_ok, fractal_ok, rejection_ok])

    if total_confirmations >= 3:
        # 🔒 CONFIRMACIÓN FINAL: Dirección coincide con Zona
        if zone == "resistencia" and direction == "put":
            return "put"
        if zone == "soporte" and direction == "call":
            return "call"

    return None


# ============================================
# 🔄 COMPATIBILIDAD CON TU BOT
# ============================================

def pro_signal(df):
    """Alias para mantener compatibilidad con tu código principal"""
    return get_signal(df)

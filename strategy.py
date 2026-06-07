import pandas as pd
import numpy as np

def get_signal(df):
    """
    ESTRATEGIA DE CICLOS: Detecta agotamiento + cambio de tendencia
    ✅ Entra como en la operación ganadora de tu imagen
    ✅ Bloquea entradas en retrocesos sin cambio real
    ✅ Mide fuerza, agotamiento y confirmación
    """
    if df is None or len(df) < 40:
        return None, 0

    data = df.copy()

    # ======================================
    # INDICADORES
    # ======================================
    data['ma_corta'] = data['close'].rolling(4).mean()
    data['ma_media'] = data['close'].rolling(10).mean()
    data['ma_larga'] = data['close'].rolling(20).mean()
    
    data['rango'] = data['high'] - data['low']
    rango_prom = data['rango'].rolling(20).mean()
    data['cuerpo'] = abs(data['close'] - data['open'])
    data['fuerza'] = np.where(data['cuerpo'] > rango_prom * 0.35, 1, 0)
    
    data['direccion'] = np.where(data['close'] > data['open'], 1, -1)
    data['fuerza_acumulada'] = data['direccion'] * data['cuerpo']
    data['tendencia_fuerza'] = data['fuerza_acumulada'].rolling(8).sum()

    # Últimas 10 velas para ver ciclo completo
    ultimas = data.tail(10).copy()
    if len(ultimas) < 10:
        return None, 0

    v10, v9, v8, v7, v6, v5, v4, v3, v2, v1 = ultimas.iloc[:10].values
    actual = ultimas.iloc[-1]

    # ======================================
    # DETECTAR AGOTAMIENTO DE TENDENCIA
    # ======================================
    # Agotamiento bajista (como en tu operación ganadora)
    agotamiento_bajista = (
        actual['tendencia_fuerza'] < -rango_prom * 3  # Bajada muy fuerte acumulada
        and abs(actual['cuerpo']) < rango_prom * 0.25  # Última vela sin fuerza
        and v2['low'] <= v3['low'] <= v4['low']  # Mínimos sucesivos
    )

    # Agotamiento alcista
    agotamiento_alcista = (
        actual['tendencia_fuerza'] > rango_prom * 3
        and abs(actual['cuerpo']) < rango_prom * 0.25
        and v2['high'] >= v3['high'] >= v4['high']
    )

    # ======================================
    # NIVELES CLAVE
    # ======================================
    resistencia = max(v10[1], v9[1], v8[1], v7[1], v6[1], v5[1], v4[1], v3[1])
    soporte = min(v10[2], v9[2], v8[2], v7[2], v6[2], v5[2], v4[2], v3[2])

    # ======================================
    # CONDICIONES DE COMPRA (CALL) - COMO EN TU GANADORA
    # ======================================
    if agotamiento_bajista:
        # Buscamos: cambio de dirección + fuerza + retroceso pequeño
        velas_alcistas = sum(1 for v in [v3, v2, actual] if v['direccion'] == 1)
        if (
            velas_alcistas >= 2
            and actual['fuerza'] == 1
            and actual['close'] > v2['high']  # Supera el retroceso
            and actual['ma_corta'] > actual['ma_media']
        ):
            return "call", 85

    # Compra por ruptura normal
    if (
        not agotamiento_alcista
        and actual['close'] > resistencia
        and actual['fuerza'] == 1
        and actual['ma_corta'] > actual['ma_larga']
    ):
        return "call", 78

    # ======================================
    # CONDICIONES DE VENTA (PUT)
    # ======================================
    if agotamiento_alcista:
        velas_bajistas = sum(1 for v in [v3, v2, actual] if v['direccion'] == -1)
        if (
            velas_bajistas >= 2
            and actual['fuerza'] == 1
            and actual['close'] < v2['low']
            and actual['ma_corta'] < actual['ma_media']
        ):
            return "put", 85

    # Venta por ruptura normal
    if (
        not agotamiento_bajista
        and actual['close'] < soporte
        and actual['fuerza'] == 1
        and actual['ma_corta'] < actual['ma_larga']
    ):
        return "put", 78

    return None, 0

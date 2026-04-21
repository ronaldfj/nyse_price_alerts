# 📈 Stock Sentinel Bot

Refactor de la estrategia de alertas para acciones con foco en entradas más limpias y menos falsos positivos.

## Qué cambia

- **Score por capas**: `regime + setup + trigger`
- **R:R estructural real**: stop por swing low + ATR buffer
- **Filtro de pendiente**: EMA200 ascendente
- **Relative Strength**: comparación simple vs `SPY` a 20 sesiones
- **Contexto manual real**: usa `market_context_stocks.json` por defecto
- **Workflow corregido**: cron con timezone y `concurrency`

## Lógica resumida

### Regime
Valida sesgo alcista de fondo:
- `Close > EMA200`
- `EMA50 > EMA200`
- `EMA200 slope > 0`
- `ADX >= 18` y `DI+ > DI-`

### Setup
Busca estructura operable:
- distancia razonable a `EMA20`
- `RSI` en rango 45–65 o recuperando
- `EMA20 > EMA50`
- fuerza relativa positiva contra `SPY`

### Trigger
Busca momento de entrada:
- ruptura de máximo reciente o reclaim de `EMA20`
- mejora de `MACD histogram`
- volumen relativo suficiente

## Variables de entorno recomendadas

- `MIN_SCORE=6.0`
- `MIN_RR=1.9`
- `COOLDOWN_HOURS=48`
- `TRIGGER_VOL_RATIO=1.4`
- `SETUP_RSI_MIN=45`
- `SETUP_RSI_MAX=65`
- `RS_LOOKBACK=20`
- `SWING_LOOKBACK=12`

## Archivos clave

- `alert_v2.py`
- `stocks-alert-v2.yml`
- `requirements-v2.txt`
- `market_context_stocks.json`

## Siguiente iteración sugerida

Llevar la arquitectura a **multi-timeframe**:
- Diario para regime
- 60m para setup
- 15m para trigger

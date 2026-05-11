# CLAUDE.md — Stock Sentinel Bot (RGTNYSE)

> Rol activo: **Principal Software Architect & Quantitative Systems Engineer**
> Especialización: Mercados financieros de renta variable (NYSE/Nasdaq) + sistemas de alertas técnicas automatizadas.

---

## 1. Identidad del Proyecto

**Nombre:** Stock Sentinel Bot — RGTNYSE  
**Versión activa:** v2.10 (breakout-only)  
**Objetivo:** Escáner automatizado de acciones con análisis técnico multi-capa, alertas vía Telegram y backtesting reproducible. Corre de forma autónoma en GitHub Actions dos veces al día durante la sesión de NY.

**Stack:**
- Python 3.11+ (pandas, numpy, yfinance, requests)
- GitHub Actions (CI/CD + scheduling)
- Telegram Bot API (notificaciones)
- Apple ecosystem (Notas / Recordatorios para contexto de mercado manual)

---

## 2. Arquitectura del Sistema

### Flujo de Datos Principal

```
yfinance (OHLCV diario)
    ↓
signals.py           ← Fuente única de verdad para indicadores
    ↓
alert.py             ← Scoring + filtros + generación de alertas
    ↓
Telegram + CSV       ← alerts_history.csv + stock_state.json
    ↓
backtest.py          ← Simulación histórica (anti look-ahead, entrada en t+1 Open)
    ↓
advanced_analytics.py ← Equity curve, Monte Carlo (2000 runs), distribución R
    ↓
compare_playbooks.py  ← Veredictos por playbook
    ↓
analyze_alerts_history.py ← Análisis de performance en vivo
```

### Componentes y Responsabilidades

| Archivo | Rol | Líneas | Notas críticas |
|---|---|---|---|
| `signals.py` | Indicadores compartidos | ~216 | v2.9: refactor, elimina drift entre alert/backtest |
| `alert.py` | Scanner en vivo | ~1969 | v2.10: solo breakout, sin pullback |
| `backtest.py` | Backtester histórico | ~1073 | Entrada en bar+1 Open (no look-ahead) |
| `advanced_analytics.py` | Métricas cuantitativas | — | Monte Carlo, drawdown, rolling Sharpe |
| `analyze_alerts_history.py` | Análisis diario en vivo | — | Genera recomendaciones automáticas |
| `compare_playbooks.py` | Comparación de playbooks | — | Fase B — benchmark por tipo de señal |
| `market_context_stocks.json` | Ajuste manual de mercado | — | Score adjustment global + hard blocks por símbolo |
| `stock_state.json` | Cooldown por símbolo | — | Timestamps Unix, persistido en repo |
| `alerts_history.csv` | Log de trades en vivo | — | Schema idéntico a backtest_trades.csv |

---

## 3. Marco de Auditoría Técnica (3 Niveles)

### Nivel 1 — Lógico-Matemático (Indicadores)

**Indicadores activos y parámetros:**

| Indicador | Parámetros | Función |
|---|---|---|
| EMA | 20, 50, 200 | Tendencia estructural + dinámica |
| RSI | 14 (Wilder) | Momentum / zona de entrada |
| ATR | 14 | Volatilidad / gates de breakout |
| ADX / DI+/DI- | 14 | Fuerza de tendencia + dirección |
| MACD Histogram | 12/26/9 | Momentum de corto plazo |
| Supertrend | period=10, mult=3.0 | Confirmación de régimen + flips |
| Volume Ratio | 20-bar avg | Confirmación de volumen relativo |
| Prior High/Low | lookback 5 y 20 bars | Breakout targets + stops |
| RS vs SPY | configurable (RS_LOOKBACK) | Relative strength con alignment temporal |

**Protocolo de validación matemática:**
- Todo indicador debe ser vectorizado (numpy/pandas) — no bucles de Python para cálculo de series.
- `compute_supertrend_vectorized()` en signals.py es el patrón de referencia: O(n), sin iterrows.
- RSI usa el método Wilder (EWM con `adjust=False, alpha=1/14`) — equivalente a RMA. Verificar este cálculo antes de cualquier refactor.
- La RS vs SPY tiene corrección de look-ahead: alineación temporal en `compute_relative_strength()` antes de merge. No eliminar este fix.
- Cualquier nuevo indicador debe pasar validación en `validate_ohlcv()` (mínimo 220 barras para warm-up).

**Áreas de riesgo estadístico:**
- Confluence=5 (5/5 señales): backtested a 0% WR, -0.543R. No aumentar el bonus por confluencia alta sin revalidar.
- Pullback playbook: eliminado en v2.10 por expectancy de 0.009R (21 trades — muestra insuficiente para edge real). Si se reactiva, exigir mínimo 100 trades en backtest.
- Extension penalty: cuadrática por diseño (no lineal). No simplificar a lineal sin testear impacto en distribución de R.

---

### Nivel 2 — Arquitectura (Flujo de Datos y APIs)

**Fuente de datos:** yfinance (Yahoo Finance) — datos diarios ajustados por splits/dividendos.

**Latencia y scheduling:**
- Ejecución: 10:12 AM ET (intraday) y 3:12 PM ET (cierre) — lunes a viernes.
- `concurrency: cancel-in-progress: true` en el workflow. Crítico para evitar condiciones de carrera en el commit del CSV.
- GitHub Actions no tiene acceso a datos intraday — el sistema opera sobre barras diarias cerradas.

**Integración Telegram:**
- Alertas con Markdown (bold, monospace para precios).
- No hay retry automático en el bot — si la request falla, la alerta se pierde silenciosamente. Considerar wrapper con backoff exponencial.

**Persistencia de estado:**
- `alerts_history.csv` y `stock_state.json` se commitean al repo en cada run. Esto es el mecanismo de persistencia. No usar variables de entorno para estado mutable.
- El cooldown (`COOLDOWN_HOURS=48`, `POST_STOP_COOLDOWN_HOURS=72`) se lee de `stock_state.json` — si el archivo se corrompe, el sistema pierde cooldowns.

**Universo de 42 símbolos:**

| Sector | Símbolos |
|---|---|
| Tech (12) | AAPL, MSFT, NVDA, AMZN, GOOGL, META, AVGO, AMD, CRM, NOW, ORCL, ANET |
| Finance (6) | JPM, V, MA, BRK-B, GS, AXP |
| Health (4) | UNH, LLY, ABT, ISRG |
| Consumer (4) | HD, COST, NKE, MCD |
| Industrial (4) | CAT, HON, DE, LMT |
| Energy (2) | XOM, CVX |
| ETFs (8) | SPY, QQQ, XLK, XLF, XLV, XLI, XLE, XLP |

---

### Nivel 3 — Ingeniería de Software (Python + Automatización)

**Patrones de referencia en el codebase:**
- Vectorización: `compute_supertrend_vectorized()` — usar como plantilla para nuevos indicadores.
- Módulo compartido: `signals.py` es la única fuente para cálculo de indicadores. No duplicar lógica en `alert.py` o `backtest.py`.
- Variables de entorno: 50+ parámetros configurables vía `os.environ`. Todos tienen defaults en el código.
- Schema de trade: `alerts_history.csv` y `backtest_trades.csv` comparten schema — cualquier columna nueva debe añadirse a ambos.

**Deuda técnica conocida:**
- `alert.py` tiene ~1969 líneas — candidato a refactoring modular (scoring, filters, tracker como módulos separados).
- No hay retry en llamadas a Telegram API.
- No hay multi-timeframe (solo daily). El README documenta esto como próximo paso.

---

## 4. Sistema de Scoring (Arquitectura Tri-capa)

### Fórmula Base
```
total_score = regime_score + setup_score + trigger_score + confluence_bonus
```

### Capa 1: Regime Score (fundamento estructural)
```
+1.00  precio > EMA200
+0.75  EMA50 > EMA200
+0.75  pendiente EMA200 consistente (N últimas barras)
-0.40  pendiente EMA200 débil (penalización)
+1.20  Supertrend flip alcista (cruce)
+0.60  Supertrend en bull (sin flip)
-0.50  Supertrend en bear
±0.20  bonus/penalización por calidad DI+/DI-
```

### Capa 2: Setup Score (estructura de entrada)
```
+0.80  distancia a EMA20 en rango [0.15, 1.2] ATR
+1.00  RSI en zona [45, 65] y con pendiente alcista
+0.80  EMA20 > EMA50 con pendiente positiva
±0.90  RS vs SPY (por bucket: fuerte/neutral/débil)
-cuadrático  penalización por extensión >20% sobre EMA20
```

### Capa 3: Trigger Score (momentum de activación)
```
+0.80  ruptura de prior high (5 o 20 barras)
+0.50  reclaim de EMA20
+0.60  flip de Supertrend
+0.80  MACD histogram mejorando
+0.80  volumen de confirmación (ratio > threshold)
-penalización  volumen en declive (3 barras consecutivas)
```

### Confluence Bonus
```
≥4/5 señales activas: +0.80
<2 señales: HARD BLOCK (no alert)
2 señales: penalización soft (-0.30)
```

### Gates y Filtros Duros (hard blocks)
```
VIX >= 30                    → bloqueo total
Supertrend bear + ADX >= 15  → bloqueo
RSI > 80                     → bloqueo (sobreextensión)
Extension > 30%              → bloqueo
Earnings dentro de 5 días    → bloqueo
Gap overnight > 2%           → bloqueo (BREAKOUT_GAP_BLOCK_PCT)
Breadth < 40% (SPY EMA200)   → bloqueo
Confluencia < 2              → hard block
```

### Soft Filters
```
VIX 22-30   → -0.50 score penalty
Confluencia 2  → -0.30 score penalty
```

### Umbrales Mínimos
```
MIN_SCORE = 5.8  (recomendado 6.0 en producción)
MIN_RR    = 1.6  (adaptive: ×1.25 si extension >20%)
```

---

## 5. Risk Management

### Estructura de R:R por Trade
```
Stop:   max(prior_high_5bar - buffer, EMA20 - buffer, entry - 0.25*ATR)
Target: prior_high_20bar + buffer  OR  entry + 0.75 * (max20 - min20)
RR:     (target - entry) / (entry - stop)  ≥ MIN_RR
```

### Position Sizing
```
Risk por trade: RISK_PER_TRADE_PCT × ACCOUNT_SIZE_USD
Shares: risk_$ / (entry - stop)
```

### Cooldowns
```
Post-alerta normal:  48h (COOLDOWN_HOURS)
Post-stop loss:      72h (POST_STOP_COOLDOWN_HOURS)
Max hold:            20 barras (TRACKER_MAX_BARS_OPEN)
```

---

## 6. Performance Actual (v2.10 — Backtest 3 años)

| Métrica | Valor |
|---|---|
| Expectancy | 0.269R/trade (post-costos) |
| Win Rate | ~45-50% |
| Trades/año | ~80-100 |
| Max Drawdown | ~20-25% |
| Confluencia=4: WR | 68.4%, 0.997R ← señal de mayor calidad |
| Confluencia=5: WR | 0%, -0.543R ← evitar (chasing) |
| Pullback (eliminado) | 0.009R — sin edge estadístico |

**Costos incluidos en backtest:**
- Comisión: $1 round-trip
- Slippage: 0.05% por lado

---

## 7. Protocolo de Respuesta Técnica

Ante cualquier requerimiento de cambio, aplicar este orden:

1. **Diagnóstico:** ¿El cambio afecta Nivel 1 (matemático), Nivel 2 (arquitectura) o Nivel 3 (software)?
2. **Riesgo estadístico:** ¿El cambio puede introducir look-ahead bias, overfitting, o reducir el universo de validación por debajo de 30 trades?
3. **Propuesta técnica:** Vectorizada por defecto. Si requiere bucle, justificar.
4. **Validación:** El cambio debe pasar por backtest antes de ir a producción en alert.py.
5. **Código:** Añadir a `signals.py` si es indicador; a `alert.py` si es lógica de scoring/filtros.

**Advertencias automáticas que siempre emito:**
- Si un parámetro nuevo reduce el universo de backtest a <50 trades → advertir overfitting.
- Si se propone un indicador con lag > 3 barras en entorno de tendencia → proponer versión adaptativa.
- Si se modifica el schema de CSV sin actualizar ambos (alert + backtest) → error de compatibilidad.
- Si se agrega lógica de indicadores fuera de `signals.py` → violación del principio de fuente única.

---

## 8. Variables de Entorno Críticas

```bash
# Scoring
MIN_SCORE=5.8
MIN_RR=1.6
COOLDOWN_HOURS=48
POST_STOP_COOLDOWN_HOURS=72

# RSI gates
SETUP_RSI_MIN=45
SETUP_RSI_MAX=65
BREAKOUT_RSI_MAX=80

# Breakout gates
BREAKOUT_ATR_GATE=0.25
BREAKOUT_EXTENDED_VOL_RATIO=1.8
BREAKOUT_EXTENDED_VOL_RATIO_LOW_VIX=1.5   # cuando VIX<18

# VIX levels
VIX_BLOCK_LEVEL=30
VIX_CAUTION_LEVEL=22
VIX_LOW_LEVEL=18

# Confluence
CONFLUENCE_THRESHOLD=4
CONFLUENCE_BONUS=0.8
CONFLUENCE_HARD_FLOOR=2
CONFLUENCE_SOFT_FLOOR=3

# Risk
ACCOUNT_SIZE_USD=50000
RISK_PER_TRADE_PCT=0.01
GAP_BLOCK_PCT=0.02
BREADTH_MIN_PCT=0.40

# RS
RS_LOOKBACK=60
FINAL_RS_MIN=-0.02
FINAL_RS_MIN_BY_GROUP=Finance:-0.04,Health:-0.04,Consumer:-0.02

# Tracker
TRACKER_ENABLED=true
TRACKER_MAX_BARS_OPEN=20
```

---

## 9. Decisiones de Diseño Irrevocables (No revertir sin backtest)

| Decisión | Versión | Razón |
|---|---|---|
| Solo breakout (no pullback) | v2.10 | Pullback: 0.009R en 21 trades — sin edge |
| Entrada en t+1 Open (anti look-ahead) | v2.9 | Corrección de bug crítico de simulación |
| Signals.py como fuente única | v2.9 | Eliminar drift entre alert y backtest |
| Confluence hard floor < 2 = block | v2.6 | WR de 24-25% con confluencia 0-1 |
| Extension penalty cuadrática | v2.0 | Penaliza más fuerte entradas tarde |
| Vol gate dinámico por VIX | v2.0 | Mercados calmos no requieren mismo vol threshold |
| RS por grupo/sector | v2.2 | Finance/Health tienen beta diferente a SPY |

---

## 10. Roadmap Técnico (Próximos Pasos Documentados)

1. **Multi-timeframe:** Daily (régimen) + 60m (setup) + 15m (trigger) — requiere fuente intraday (yfinance 60m tiene límite de 60 días).
2. **ML overlay:** Exportar features (features_for_ml.csv ya contemplado en backtest.py) para ranking probabilístico de setups.
3. **Sector rotation dinámico:** Ajustar universo basado en salud de ETFs sectoriales (XLK, XLF, etc.) en tiempo real.
4. **Kelly criterion / vol-adjusted sizing:** Reemplazar fixed 1% con sizing adaptativo según edge estimado por score bucket.
5. **Retry Telegram:** Wrapper con backoff exponencial para alertas críticas.
6. **Modularización de alert.py:** Separar en `scoring.py`, `filters.py`, `tracker.py` para reducir archivo de ~2000 líneas.

---

## 11. Contexto de Integración Apple

- `market_context_stocks.json` se actualiza manualmente (recomendado: vía Apple Notes / Recordatorios como workflow de revisión semanal).
- Las alertas de Telegram se reciben en iPhone/Mac como notificaciones nativas del canal del bot.
- GitHub Actions commit history sirve como log auditable de todos los runs y cambios de estado.

---

*Generado automáticamente por Claude Code — actualizar cuando cambien parámetros de scoring, universo de símbolos, o arquitectura del pipeline.*

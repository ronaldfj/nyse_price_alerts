Ejecuta el scanner de Stock Sentinel Bot en modo dry-run y resume el resultado.

## Pasos (sin exploración adicional)

**1. Lee `.github/workflows/stocks-alert.yml`** — extrae todos los `env:` del job `run-alert` (sección "Ejecutar scanner").

**2. Construye el comando con esos env vars y ejecuta:**

```bash
source .venv/bin/activate && DRY_RUN=true \
  BREAKOUT_RSI_MAX=<valor> COOLDOWN_HOURS=<valor> MIN_SCORE=<valor> \
  MIN_RR=<valor> SETUP_RSI_MIN=<valor> SETUP_RSI_MAX=<valor> \
  REQUIRE_PLAYBOOK=<valor> ALERT_ETFS=<valor> \
  TRACKER_ENABLED=<valor> TRACKER_MAX_BARS_OPEN=<valor> \
  POST_STOP_COOLDOWN_HOURS=<valor> CORRELATION_GUARD_ENABLED=<valor> \
  BREADTH_ENABLED=<valor> BREADTH_MIN_PCT=<valor> BREADTH_BLOCK_BELOW=<valor> \
  CONFLUENCE_THRESHOLD=<valor> CONFLUENCE_BONUS=<valor> \
  CONFLUENCE_HARD_FLOOR=<valor> CONFLUENCE_SOFT_FLOOR=<valor> \
  BREAKOUT_ATR_GATE=<valor> BREAKOUT_MAX_ATR=<valor> \
  BREAKOUT_EXTENDED_VOL_RATIO=<valor> BREAKOUT_EXTENDED_VOL_RATIO_LOW_VIX=<valor> \
  VIX_BLOCK_LEVEL=<valor> VIX_CAUTION_LEVEL=<valor> VIX_LOW_LEVEL=<valor> \
  FINAL_RS_MIN=<valor> RS_LOOKBACK=<valor> \
  FINAL_RS_MIN_BY_GROUP=<valor> \
  ACCOUNT_SIZE_USD=<valor> RISK_PER_TRADE_PCT=<valor> \
  GAP_BLOCK_PCT=<valor> GAP_FILTER_ENABLED=<valor> \
  python alert.py 2>&1 | tail -60
```

Reemplaza `<valor>` con los valores reales del workflow antes de ejecutar.

**3. Reporta exactamente esto:**

- **Línea de resumen final** del log (`Escaneo v2.6 completado | ...`)
- **Símbolos en cooldown** y cuántas horas restan
- **Candidatos con señal** (si los hay): símbolo, score, playbook, RR
- **Errores o excepciones** en el log (busca `ERROR` o `Exception`)
- **Estado del mercado**: VIX, breadth, si hay bloqueo macro activo

Si el script falla, muestra las últimas 20 líneas del error. No leas otros archivos del proyecto.

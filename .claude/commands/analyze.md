Analiza el historial de alertas del Stock Sentinel Bot (RGTNYSE) y reporta el estado de performance en vivo.

## Pasos (ejecutar en orden, sin exploración adicional)

**1. Lee el archivo `alerts_history.csv` completo.**

**2. Ejecuta este script Python para calcular todas las métricas:**

```bash
python3 - << 'EOF'
import csv
from collections import defaultdict

rows = []
with open('alerts_history.csv', newline='') as f:
    reader = csv.DictReader(f)
    for row in reader:
        rows.append(row)

closed = [r for r in rows if r['status'] not in ('open', '')]
open_trades = [r for r in rows if r['status'] == 'open']

print(f"=== RESUMEN ===")
print(f"Total alertas: {len(rows)} | Cerradas: {len(closed)} | Abiertas: {len(open_trades)}")

# R por trade
total_r, wins, losses = 0, 0, 0
for r in closed:
    if not r.get('exit_price'): continue
    entry, stop, exit_p = float(r['price']), float(r['stop']), float(r['exit_price'])
    r_val = (exit_p - entry) / (entry - stop)
    total_r += r_val
    wins += (1 if r_val > 0 else 0)
    losses += (0 if r_val > 0 else 1)

n = wins + losses
print(f"\n=== PERFORMANCE (trades con exit_price) ===")
print(f"WR: {wins}/{n} = {wins/n*100:.1f}%" if n else "Sin trades cerrados")
print(f"Avg R/trade: {total_r/n:+.3f}R" if n else "")
print(f"Total R acumulado: {total_r:+.2f}R" if n else "")
print(f"Backtest esperado: +0.269R")

# Por RSI
print(f"\n=== POR RSI EN ENTRADA ===")
rsi_b = {'<65': [], '65-70': [], '70-75': [], '75+': []}
for r in closed:
    if not r.get('exit_price'): continue
    rsi = float(r['rsi'])
    entry, stop, exit_p = float(r['price']), float(r['stop']), float(r['exit_price'])
    rv = (exit_p - entry) / (entry - stop)
    if rsi < 65: rsi_b['<65'].append(rv)
    elif rsi < 70: rsi_b['65-70'].append(rv)
    elif rsi < 75: rsi_b['70-75'].append(rv)
    else: rsi_b['75+'].append(rv)
for b, vals in rsi_b.items():
    if vals:
        print(f"  RSI {b}: {len(vals)} trades | avg={sum(vals)/len(vals):+.2f}R | WR={sum(1 for v in vals if v>0)/len(vals)*100:.0f}%")

# Por extension
print(f"\n=== POR EXTENSIÓN SOBRE EMA200 ===")
ext_b = {'<10%': [], '10-20%': [], '20-30%': [], '30%+': []}
for r in closed:
    if not r.get('exit_price'): continue
    ext = float(r['extension_pct'])
    entry, stop, exit_p = float(r['price']), float(r['stop']), float(r['exit_price'])
    rv = (exit_p - entry) / (entry - stop)
    if ext < 10: ext_b['<10%'].append(rv)
    elif ext < 20: ext_b['10-20%'].append(rv)
    elif ext < 30: ext_b['20-30%'].append(rv)
    else: ext_b['30%+'].append(rv)
for b, vals in ext_b.items():
    if vals:
        print(f"  Ext {b}: {len(vals)} trades | avg={sum(vals)/len(vals):+.2f}R | WR={sum(1 for v in vals if v>0)/len(vals)*100:.0f}%")

# Por exit reason
print(f"\n=== POR EXIT REASON ===")
by_exit = defaultdict(list)
for r in closed:
    if not r.get('exit_price'): continue
    entry, stop, exit_p = float(r['price']), float(r['stop']), float(r['exit_price'])
    rv = (exit_p - entry) / (entry - stop)
    by_exit[r['exit_reason']].append(rv)
for k, vals in sorted(by_exit.items()):
    print(f"  {k}: {len(vals)} | avg={sum(vals)/len(vals):+.2f}R")

# Concentración: posiciones abiertas por símbolo
print(f"\n=== POSICIONES ABIERTAS ===")
open_by_sym = defaultdict(list)
for r in open_trades:
    open_by_sym[r['symbol']].append(r)
for sym, trades in sorted(open_by_sym.items(), key=lambda x: -len(x[1])):
    bars = [int(t.get('bars_open') or 0) for t in trades]
    pnls = [float(t.get('pnl_pct') or 0) for t in trades]
    print(f"  {sym}: {len(trades)} posicion(es) | bars={bars} | pnl={[f'{p:+.1f}%' for p in pnls]}")

# Alertas por símbolo (cooldown check)
print(f"\n=== SÍMBOLOS CON MÚLTIPLES ALERTAS (verificar cooldown) ===")
sym_ts = defaultdict(list)
for r in rows:
    sym_ts[r['symbol']].append(r['timestamp_utc'][:10])
for sym, dates in sorted(sym_ts.items()):
    if len(dates) > 1:
        print(f"  {sym}: {len(dates)} alertas → {dates}")
EOF
```

**3. Reporta los hallazgos en este formato:**

- **Performance global**: WR, Avg R/trade, comparación vs backtest (+0.269R esperado)
- **Hallazgos por bucket** (RSI, extensión): qué categorías están sobre/bajo-performando
- **Posiciones abiertas**: concentración por símbolo, trades estancados (>15 bars)
- **Flags de parámetros**: si algún bucket muestra un patrón claro que justifique cambio
- **Muestra insuficiente**: advertir si hay <30 trades cerrados (riesgo de overfitting)

Sé conciso. No leas otros archivos del proyecto. Si hay menos de 15 trades cerrados, menciona que el análisis es preliminar.

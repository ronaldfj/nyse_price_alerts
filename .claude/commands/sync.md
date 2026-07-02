Sincroniza el repositorio local con GitHub y resume los cambios relevantes del bot.

## Pasos

**1. Ejecuta git pull:**

```bash
git pull origin main
```

**2. Si hubo cambios, analiza qué se actualizó:**

```bash
python3 - << 'EOF'
import csv, json
from collections import defaultdict

# Alertas nuevas o actualizadas
try:
    rows = []
    with open('alerts_history.csv', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    open_trades = [r for r in rows if r['status'] == 'open']
    closed_today = [r for r in rows if r['status'] not in ('open', '') and r.get('closed_utc', '')]
    
    print(f"CSV: {len(rows)} alertas totales | {len(open_trades)} abiertas | {len(closed_today)} cerradas")
    
    # Posiciones abiertas resumidas
    print("\nAbiertas:")
    for r in sorted(open_trades, key=lambda x: int(x.get('bars_open') or 0), reverse=True):
        bars = r.get('bars_open', '?')
        pnl = float(r.get('pnl_pct') or 0)
        sym = r['symbol']
        pb = r.get('playbook', '')
        print(f"  {sym:6s} {pb:9s} bars={bars:>2} pnl={pnl:+.1f}%")
    
    # Cerrados recientemente (últimos 5)
    recently_closed = sorted(
        [r for r in rows if r.get('closed_utc')],
        key=lambda x: x.get('closed_utc', ''),
        reverse=True
    )[:5]
    if recently_closed:
        print("\nÚltimos cierres:")
        for r in recently_closed:
            entry = float(r['price']); stop = float(r['stop'])
            exit_p = float(r['exit_price']) if r.get('exit_price') else None
            r_val = (exit_p - entry) / (entry - stop) if exit_p else None
            r_str = f"{r_val:+.2f}R" if r_val is not None else "?"
            print(f"  {r['symbol']:6s} {r.get('exit_reason',''):20s} {r_str} ({r.get('closed_utc','')[:10]})")

except Exception as e:
    print(f"Error leyendo CSV: {e}")

# Stock state
try:
    with open('stock_state.json') as f:
        state = json.load(f)
    print(f"\nstock_state.json: {len(state)} símbolos con cooldown activo")
    print(f"  {sorted(state.keys())}")
except Exception as e:
    print(f"Error leyendo state: {e}")
EOF
```

**3. Reporta:**

- Si no hubo cambios: "Sin cambios desde el último run."
- Si hubo cambios: muestra el output del script + cuántos commits llegaron y de qué fecha
- Si hay posiciones en pérdida >3% o abiertas >18 bars: mencionarlo explícitamente como flag

No leas otros archivos. No ejecutes más comandos de los indicados.

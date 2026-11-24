# Advanced Analytics Report

- Archivo: `alerts_history.csv`
- Trades cerrados: **63**
- Capital inicial: **$10,000**
- Riesgo por trade: **1.0%**
- Comision: **$1.0** | Slippage: **0.05%** por lado

## Equity Curve (con compounding)

- Capital final: **$9,598.37**
- Retorno total: **-4.02%**
- Max drawdown: **-15.70%**
- Trades en drawdown: **58/63 (92.1%)**

## Distribucion de R (sin costos)

- **n**: 63
- **mean**: -0.055
- **median**: -1.0
- **std**: 1.445
- **min**: -1.0
- **max**: 4.523
- **q05**: -1.0
- **q25**: -1.0
- **q75**: 0.949
- **q95**: 2.521
- **skew**: 1.605
- **kurtosis**: 2.1
- **winning_trades**: 20
- **losing_trades**: 43
- **expectancy**: -0.055
- **win_rate_pct**: 31.75

## Distribucion de R (con costos)

- Expectancy original: **-0.055R**
- Expectancy con costos: **-0.094R**
- Degradacion por costos: **-0.039R/trade**

## Distribucion por bucket de R

| bucket     |   n |   pct |
|:-----------|----:|------:|
| < -1.5R    |   0 |   0   |
| -1.5 a -1R |   0 |   0   |
| -1 a -0.5R |  39 |  61.9 |
| -0.5 a 0R  |   4 |   6.3 |
| 0 a 0.5R   |   0 |   0   |
| 0.5 a 1R   |   5 |   7.9 |
| 1 a 1.5R   |   6 |   9.5 |
| 1.5 a 2R   |   4 |   6.3 |
| 2 a 3R     |   2 |   3.2 |
| 3 a 5R     |   3 |   4.8 |
| > 5R       |   0 |   0   |

## Monte Carlo (1000 simulaciones)

- Capital final mediano: **$9,574.08**
- Capital final p05 (peor 5%): **$8,002.44**
- Capital final p95 (mejor 5%): **$11,702.09**
- Drawdown mediano: **-12.41%**
- Drawdown p95 (peor caso): **-22.13%**
- Mediana de prob. de ganar dinero: **34.8%**
- Max losses consecutivas (p95): **15**
- Max losses consecutivas peor caso: **23**

## Rolling Metrics (ventana=30 trades)

- Sharpe rolling promedio: **-0.227**
- Sharpe rolling min: **-0.542**
- Sharpe rolling max: **0.079**
- Mean R primera mitad: **-0.254R**
- Mean R segunda mitad: **-0.211R**
- Edge degradation: **+0.043R**

## Time Exposure

- **n_trades**: 63
- **total_days**: 212
- **avg_bars_per_trade**: 10.78
- **median_bars**: 9.0
- **max_bars**: 20
- **time_in_market_pct**: 100.0

## Veredicto cuantitativo

⛔ **Sistema NO rentable con costos reales**

🟢 **Edge estable** — sin degradacion notable entre periodos
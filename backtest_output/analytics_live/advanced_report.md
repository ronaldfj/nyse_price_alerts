# Advanced Analytics Report

- Archivo: `alerts_history.csv`
- Trades cerrados: **45**
- Capital inicial: **$10,000**
- Riesgo por trade: **1.0%**
- Comision: **$1.0** | Slippage: **0.05%** por lado

## Equity Curve (con compounding)

- Capital final: **$9,986.43**
- Retorno total: **-0.14%**
- Max drawdown: **-15.70%**
- Trades en drawdown: **40/45 (88.9%)**

## Distribucion de R (sin costos)

- **n**: 45
- **mean**: 0.009
- **median**: -1.0
- **std**: 1.58
- **min**: -1.0
- **max**: 4.523
- **q05**: -1.0
- **q25**: -1.0
- **q75**: 0.968
- **q95**: 3.729
- **skew**: 1.566
- **kurtosis**: 1.721
- **winning_trades**: 15
- **losing_trades**: 30
- **expectancy**: 0.009
- **win_rate_pct**: 33.33

## Distribucion de R (con costos)

- Expectancy original: **0.009R**
- Expectancy con costos: **-0.03R**
- Degradacion por costos: **-0.039R/trade**

## Distribucion por bucket de R

| bucket     |   n |   pct |
|:-----------|----:|------:|
| < -1.5R    |   0 |   0   |
| -1.5 a -1R |   0 |   0   |
| -1 a -0.5R |  28 |  62.2 |
| -0.5 a 0R  |   2 |   4.4 |
| 0 a 0.5R   |   0 |   0   |
| 0.5 a 1R   |   4 |   8.9 |
| 1 a 1.5R   |   4 |   8.9 |
| 1.5 a 2R   |   2 |   4.4 |
| 2 a 3R     |   2 |   4.4 |
| 3 a 5R     |   3 |   6.7 |
| > 5R       |   0 |   0   |

## Monte Carlo (1000 simulaciones)

- Capital final mediano: **$9,950.61**
- Capital final p05 (peor 5%): **$8,412.48**
- Capital final p95 (mejor 5%): **$12,012.44**
- Drawdown mediano: **-9.91%**
- Drawdown p95 (peor caso): **-18.63%**
- Mediana de prob. de ganar dinero: **48.1%**
- Max losses consecutivas (p95): **13**
- Max losses consecutivas peor caso: **27**

## Rolling Metrics (ventana=30 trades)

- Sharpe rolling promedio: **-0.260**
- Sharpe rolling min: **-0.542**
- Sharpe rolling max: **0.079**
- Mean R primera mitad: **-0.078R**
- Mean R segunda mitad: **-0.440R**
- Edge degradation: **-0.362R**

## Time Exposure

- **n_trades**: 45
- **total_days**: 102
- **avg_bars_per_trade**: 10.38
- **median_bars**: 9.0
- **max_bars**: 20
- **time_in_market_pct**: 100.0

## Veredicto cuantitativo

⛔ **Sistema NO rentable con costos reales**

⚠️ **Edge degradandose** — segunda mitad rinde menos que la primera (posible overfitting)
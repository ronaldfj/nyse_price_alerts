# Advanced Analytics Report

- Archivo: `alerts_history.csv`
- Trades cerrados: **11**
- Capital inicial: **$10,000**
- Riesgo por trade: **1.0%**
- Comision: **$1.0** | Slippage: **0.05%** por lado

## Equity Curve (con compounding)

- Capital final: **$11,170.96**
- Retorno total: **+11.71%**
- Max drawdown: **-1.99%**
- Trades en drawdown: **6/11 (54.5%)**

## Distribucion de R (sin costos)

- **n**: 11
- **mean**: 1.038
- **median**: -0.427
- **std**: 2.405
- **min**: -1.0
- **max**: 4.52
- **q05**: -1.0
- **q25**: -1.0
- **q75**: 3.285
- **q95**: 4.48
- **skew**: 0.581
- **kurtosis**: -1.669
- **winning_trades**: 5
- **losing_trades**: 6
- **expectancy**: 1.038
- **win_rate_pct**: 45.45

## Distribucion de R (con costos)

- Expectancy original: **1.038R**
- Expectancy con costos: **0.998R**
- Degradacion por costos: **-0.040R/trade**

## Distribucion por bucket de R

| bucket     |   n |   pct |
|:-----------|----:|------:|
| < -1.5R    |   0 |   0   |
| -1.5 a -1R |   5 |  45.5 |
| -1 a -0.5R |   0 |   0   |
| -0.5 a 0R  |   1 |   9.1 |
| 0 a 0.5R   |   0 |   0   |
| 0.5 a 1R   |   0 |   0   |
| 1 a 1.5R   |   1 |   9.1 |
| 1.5 a 2R   |   0 |   0   |
| 2 a 3R     |   1 |   9.1 |
| 3 a 5R     |   3 |  27.3 |
| > 5R       |   0 |   0   |

## Monte Carlo (1000 simulaciones)

- Capital final mediano: **$11,125.99**
- Capital final p05 (peor 5%): **$9,851.36**
- Capital final p95 (mejor 5%): **$12,649.47**
- Drawdown mediano: **-2.82%**
- Drawdown p95 (peor caso): **-5.85%**
- Mediana de prob. de ganar dinero: **93.0%**
- Max losses consecutivas (p95): **6**
- Max losses consecutivas peor caso: **11**

## Time Exposure

- **n_trades**: 11
- **total_days**: 36
- **avg_bars_per_trade**: 7.55
- **median_bars**: 7.0
- **max_bars**: 20
- **time_in_market_pct**: 100.0

## Veredicto cuantitativo

✅ **Sistema con edge robusto** — preserva expectancy bajo costos

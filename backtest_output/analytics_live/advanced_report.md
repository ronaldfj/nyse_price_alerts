# Advanced Analytics Report

- Archivo: `alerts_history.csv`
- Trades cerrados: **4**
- Capital inicial: **$10,000**
- Riesgo por trade: **1.0%**
- Comision: **$1.0** | Slippage: **0.05%** por lado

## Equity Curve (con compounding)

- Capital final: **$10,133.80**
- Retorno total: **+1.34%**
- Max drawdown: **-1.99%**
- Trades en drawdown: **3/4 (75.0%)**

## Distribucion de R (sin costos)

- **n**: 4
- **mean**: 0.36
- **median**: -1.0
- **std**: 2.72
- **min**: -1.0
- **max**: 4.44
- **q05**: -1.0
- **q25**: -1.0
- **q75**: 0.36
- **q95**: 3.624
- **skew**: 2.0
- **kurtosis**: 4.0
- **winning_trades**: 1
- **losing_trades**: 3
- **expectancy**: 0.36
- **win_rate_pct**: 25.0

## Distribucion de R (con costos)

- Expectancy original: **0.36R**
- Expectancy con costos: **0.312R**
- Degradacion por costos: **-0.048R/trade**

## Distribucion por bucket de R

| bucket     |   n |   pct |
|:-----------|----:|------:|
| < -1.5R    |   0 |     0 |
| -1.5 a -1R |   3 |    75 |
| -1 a -0.5R |   0 |     0 |
| -0.5 a 0R  |   0 |     0 |
| 0 a 0.5R   |   0 |     0 |
| 0.5 a 1R   |   0 |     0 |
| 1 a 1.5R   |   0 |     0 |
| 1.5 a 2R   |   0 |     0 |
| 2 a 3R     |   0 |     0 |
| 3 a 5R     |   1 |    25 |
| > 5R       |   0 |     0 |

## Monte Carlo (1000 simulaciones)

- Capital final mediano: **$10,133.80**
- Capital final p05 (peor 5%): **$9,605.96**
- Capital final p95 (mejor 5%): **$10,720.02**
- Drawdown mediano: **-2.97%**
- Drawdown p95 (peor caso): **-3.94%**
- Mediana de prob. de ganar dinero: **68.1%**
- Max losses consecutivas (p95): **4**
- Max losses consecutivas peor caso: **4**

## Time Exposure

- **n_trades**: 4
- **total_days**: 15
- **avg_bars_per_trade**: 3.75
- **median_bars**: 3.0
- **max_bars**: 8
- **time_in_market_pct**: 100.0

## Veredicto cuantitativo

✅ **Sistema con edge robusto** — preserva expectancy bajo costos

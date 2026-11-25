# Advanced Analytics Report

- Archivo: `alerts_history.csv`
- Desde (vela de señal): **2026-07-10**
- Trades cerrados: **19**
- Capital inicial: **$10,000**
- Riesgo por trade: **1.0%**
- Comision: **$1.0** | Slippage: **0.05%** por lado

## Equity Curve (con compounding)

- Capital final: **$9,515.29**
- Retorno total: **-4.85%**
- Max drawdown: **-5.22%**
- Trades en drawdown: **18/19 (94.7%)**

## Distribucion de R (sin costos)

- **n**: 19
- **mean**: -0.256
- **median**: -1.0
- **std**: 1.041
- **min**: -1.0
- **max**: 1.928
- **q05**: -1.0
- **q25**: -1.0
- **q75**: 0.259
- **q95**: 1.643
- **skew**: 1.14
- **kurtosis**: -0.28
- **winning_trades**: 5
- **losing_trades**: 14
- **expectancy**: -0.256
- **win_rate_pct**: 26.32

## Distribucion de R (con costos)

- Expectancy original: **-0.256R**
- Expectancy con costos: **-0.293R**
- Degradacion por costos: **-0.037R/trade**

## Distribucion por bucket de R

| bucket     |   n |   pct |
|:-----------|----:|------:|
| < -1.5R    |   0 |   0   |
| -1.5 a -1R |   0 |   0   |
| -1 a -0.5R |  12 |  63.2 |
| -0.5 a 0R  |   2 |  10.5 |
| 0 a 0.5R   |   0 |   0   |
| 0.5 a 1R   |   1 |   5.3 |
| 1 a 1.5R   |   2 |  10.5 |
| 1.5 a 2R   |   2 |  10.5 |
| 2 a 3R     |   0 |   0   |
| 3 a 5R     |   0 |   0   |
| > 5R       |   0 |   0   |

## Monte Carlo (1000 simulaciones)

- Capital final mediano: **$9,527.39**
- Capital final p05 (peor 5%): **$8,892.63**
- Capital final p95 (mejor 5%): **$10,219.25**
- Drawdown mediano: **-6.87%**
- Drawdown p95 (peor caso): **-11.88%**
- Mediana de prob. de ganar dinero: **13.4%**
- Max losses consecutivas (p95): **13**
- Max losses consecutivas peor caso: **19**

## Time Exposure

- **n_trades**: 19
- **total_days**: 125
- **avg_bars_per_trade**: 11.32
- **median_bars**: 12.0
- **max_bars**: 20
- **time_in_market_pct**: 100.0

## Veredicto cuantitativo

⛔ **Sistema NO rentable con costos reales**

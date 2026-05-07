# Advanced Analytics Report

- Archivo: `alerts_history.csv`
- Trades cerrados: **3**
- Capital inicial: **$10,000**
- Riesgo por trade: **1.0%**
- Comision: **$1.0** | Slippage: **0.05%** por lado

## Equity Curve (con compounding)

- Capital final: **$10,236.16**
- Retorno total: **+2.36%**
- Max drawdown: **-1.99%**
- Trades en drawdown: **2/3 (66.7%)**

## Distribucion de R (sin costos)

- **n**: 3
- **mean**: 0.813
- **median**: -1.0
- **std**: 3.141
- **min**: -1.0
- **max**: 4.44
- **q05**: -1.0
- **q25**: -1.0
- **q75**: 1.72
- **q95**: 3.896
- **skew**: 1.732
- **kurtosis**: nan
- **winning_trades**: 1
- **losing_trades**: 2
- **expectancy**: 0.813
- **win_rate_pct**: 33.33

## Distribucion de R (con costos)

- Expectancy original: **0.813R**
- Expectancy con costos: **0.759R**
- Degradacion por costos: **-0.054R/trade**

## Distribucion por bucket de R

| bucket     |   n |   pct |
|:-----------|----:|------:|
| < -1.5R    |   0 |   0   |
| -1.5 a -1R |   2 |  66.7 |
| -1 a -0.5R |   0 |   0   |
| -0.5 a 0R  |   0 |   0   |
| 0 a 0.5R   |   0 |   0   |
| 0.5 a 1R   |   0 |   0   |
| 1 a 1.5R   |   0 |   0   |
| 1.5 a 2R   |   0 |   0   |
| 2 a 3R     |   0 |   0   |
| 3 a 5R     |   1 |  33.3 |
| > 5R       |   0 |   0   |

## Monte Carlo (1000 simulaciones)

- Capital final mediano: **$10,236.16**
- Capital final p05 (peor 5%): **$9,702.99**
- Capital final p95 (mejor 5%): **$10,798.64**
- Drawdown mediano: **-1.99%**
- Drawdown p95 (peor caso): **-2.97%**
- Mediana de prob. de ganar dinero: **70.9%**
- Max losses consecutivas (p95): **3**
- Max losses consecutivas peor caso: **3**

## Time Exposure

- **n_trades**: 3
- **total_days**: 14
- **avg_bars_per_trade**: 4.33
- **median_bars**: 4.0
- **max_bars**: 8
- **time_in_market_pct**: 92.86

## Veredicto cuantitativo

✅ **Sistema con edge robusto** — preserva expectancy bajo costos

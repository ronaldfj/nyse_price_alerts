# Advanced Analytics Report

- Archivo: `alerts_history.csv`
- Trades cerrados: **8**
- Capital inicial: **$10,000**
- Riesgo por trade: **1.0%**
- Comision: **$1.0** | Slippage: **0.05%** por lado

## Equity Curve (con compounding)

- Capital final: **$11,185.61**
- Retorno total: **+11.86%**
- Max drawdown: **-1.99%**
- Trades en drawdown: **4/8 (50.0%)**

## Distribucion de R (sin costos)

- **n**: 8
- **mean**: 1.441
- **median**: 0.775
- **std**: 2.678
- **min**: -1.0
- **max**: 4.52
- **q05**: -1.0
- **q25**: -1.0
- **q75**: 4.125
- **q95**: 4.492
- **skew**: 0.163
- **kurtosis**: -2.509
- **winning_trades**: 4
- **losing_trades**: 4
- **expectancy**: 1.441
- **win_rate_pct**: 50.0

## Distribucion de R (con costos)

- Expectancy original: **1.441R**
- Expectancy con costos: **1.399R**
- Degradacion por costos: **-0.042R/trade**

## Distribucion por bucket de R

| bucket     |   n |   pct |
|:-----------|----:|------:|
| < -1.5R    |   0 |   0   |
| -1.5 a -1R |   4 |  50   |
| -1 a -0.5R |   0 |   0   |
| -0.5 a 0R  |   0 |   0   |
| 0 a 0.5R   |   0 |   0   |
| 0.5 a 1R   |   0 |   0   |
| 1 a 1.5R   |   0 |   0   |
| 1.5 a 2R   |   0 |   0   |
| 2 a 3R     |   1 |  12.5 |
| 3 a 5R     |   3 |  37.5 |
| > 5R       |   0 |   0   |

## Monte Carlo (1000 simulaciones)

- Capital final mediano: **$11,185.61**
- Capital final p05 (peor 5%): **$10,043.01**
- Capital final p95 (mejor 5%): **$12,585.97**
- Drawdown mediano: **-1.99%**
- Drawdown p95 (peor caso): **-4.90%**
- Mediana de prob. de ganar dinero: **95.9%**
- Max losses consecutivas (p95): **5**
- Max losses consecutivas peor caso: **8**

## Time Exposure

- **n_trades**: 8
- **total_days**: 33
- **avg_bars_per_trade**: 6.25
- **median_bars**: 5.5
- **max_bars**: 15
- **time_in_market_pct**: 100.0

## Veredicto cuantitativo

✅ **Sistema con edge robusto** — preserva expectancy bajo costos

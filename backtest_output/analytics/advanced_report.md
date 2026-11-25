# Advanced Analytics Report

- Archivo: `backtest_output/backtest_trades.csv`
- Trades cerrados: **139**
- Capital inicial: **$10,000**
- Riesgo por trade: **1.0%**
- Comision: **$1.0** | Slippage: **0.05%** por lado

## Equity Curve (con compounding)

- Capital final: **$16,285.01**
- Retorno total: **+62.85%**
- Max drawdown: **-14.36%**
- Trades en drawdown: **102/139 (73.4%)**

## Distribucion de R (sin costos)

- **n**: 139
- **mean**: 0.364
- **median**: -0.184
- **std**: 1.573
- **min**: -4.124
- **max**: 4.67
- **q05**: -1.094
- **q25**: -1.0
- **q75**: 1.643
- **q95**: 2.933
- **skew**: 0.388
- **kurtosis**: -0.486
- **winning_trades**: 67
- **losing_trades**: 72
- **expectancy**: 0.364
- **win_rate_pct**: 48.2

## Distribucion de R (con costos)

- Expectancy original: **0.364R**
- Expectancy con costos: **0.321R**
- Degradacion por costos: **-0.043R/trade**

## Distribucion por bucket de R

| bucket     |   n |   pct |
|:-----------|----:|------:|
| < -1.5R    |   3 |   2.2 |
| -1.5 a -1R |   8 |   5.8 |
| -1 a -0.5R |  52 |  37.4 |
| -0.5 a 0R  |   9 |   6.5 |
| 0 a 0.5R   |   4 |   2.9 |
| 0.5 a 1R   |   5 |   3.6 |
| 1 a 1.5R   |  17 |  12.2 |
| 1.5 a 2R   |  18 |  12.9 |
| 2 a 3R     |  16 |  11.5 |
| 3 a 5R     |   7 |   5   |
| > 5R       |   0 |   0   |

## Monte Carlo (2000 simulaciones)

- Capital final mediano: **$16,120.22**
- Capital final p05 (peor 5%): **$12,077.58**
- Capital final p95 (mejor 5%): **$21,955.93**
- Drawdown mediano: **-8.63%**
- Drawdown p95 (peor caso): **-15.09%**
- Mediana de prob. de ganar dinero: **99.6%**
- Max losses consecutivas (p95): **10**
- Max losses consecutivas peor caso: **16**

## Rolling Metrics (ventana=30 trades)

- Sharpe rolling promedio: **0.207**
- Sharpe rolling min: **-0.330**
- Sharpe rolling max: **0.695**
- Mean R primera mitad: **0.087R**
- Mean R segunda mitad: **0.577R**
- Edge degradation: **+0.490R**

## Time Exposure

- **n_trades**: 139
- **total_days**: 1073
- **avg_bars_per_trade**: 10.12
- **median_bars**: 9.0
- **max_bars**: 20
- **time_in_market_pct**: 100.0

## Veredicto cuantitativo

✅ **Sistema con edge robusto** — preserva expectancy bajo costos

✅ **Edge fortaleciendose** — segunda mitad rinde mas que la primera
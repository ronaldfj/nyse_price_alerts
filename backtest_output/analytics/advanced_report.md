# Advanced Analytics Report

- Archivo: `backtest_output/backtest_trades.csv`
- Trades cerrados: **305**
- Capital inicial: **$10,000**
- Riesgo por trade: **1.0%**
- Comision: **$1.0** | Slippage: **0.05%** por lado

## Equity Curve (con compounding)

- Capital final: **$22,909.78**
- Retorno total: **+129.10%**
- Max drawdown: **-14.44%**
- Trades en drawdown: **241/305 (79.0%)**

## Distribucion de R (sin costos)

- **n**: 305
- **mean**: 0.283
- **median**: -0.456
- **std**: 1.458
- **min**: -1.0
- **max**: 4.65
- **q05**: -1.0
- **q25**: -1.0
- **q75**: 1.5
- **q95**: 2.675
- **skew**: 0.663
- **kurtosis**: -0.818
- **winning_trades**: 143
- **losing_trades**: 162
- **expectancy**: 0.283
- **win_rate_pct**: 46.89

## Distribucion de R (con costos)

- Expectancy original: **0.283R**
- Expectancy con costos: **0.236R**
- Degradacion por costos: **-0.047R/trade**

## Distribucion por bucket de R

| bucket     |   n |   pct |
|:-----------|----:|------:|
| < -1.5R    |   0 |   0   |
| -1.5 a -1R | 149 |  48.9 |
| -1 a -0.5R |   3 |   1   |
| -0.5 a 0R  |  10 |   3.3 |
| 0 a 0.5R   |  13 |   4.3 |
| 0.5 a 1R   |  23 |   7.5 |
| 1 a 1.5R   |  31 |  10.2 |
| 1.5 a 2R   |  25 |   8.2 |
| 2 a 3R     |  41 |  13.4 |
| 3 a 5R     |  10 |   3.3 |
| > 5R       |   0 |   0   |

## Monte Carlo (2000 simulaciones)

- Capital final mediano: **$22,690.50**
- Capital final p05 (peor 5%): **$15,070.11**
- Capital final p95 (mejor 5%): **$34,003.09**
- Drawdown mediano: **-10.71%**
- Drawdown p95 (peor caso): **-18.05%**
- Mediana de prob. de ganar dinero: **100.0%**
- Max losses consecutivas (p95): **12**
- Max losses consecutivas peor caso: **18**

## Rolling Metrics (ventana=30 trades)

- Sharpe rolling promedio: **0.175**
- Sharpe rolling min: **-0.402**
- Sharpe rolling max: **0.401**
- Mean R primera mitad: **0.219R**
- Mean R segunda mitad: **0.325R**
- Edge degradation: **+0.106R**

## Time Exposure

- **n_trades**: 305
- **avg_bars_per_trade**: 8.73

## Veredicto cuantitativo

✅ **Sistema con edge robusto** — preserva expectancy bajo costos

✅ **Edge fortaleciendose** — segunda mitad rinde mas que la primera
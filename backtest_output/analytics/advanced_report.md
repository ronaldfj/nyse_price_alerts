# Advanced Analytics Report

- Archivo: `backtest_output/backtest_trades.csv`
- Trades cerrados: **570**
- Capital inicial: **$10,000**
- Riesgo por trade: **1.0%**
- Comision: **$1.0** | Slippage: **0.05%** por lado

## Equity Curve (con compounding)

- Capital final: **$35,828.45**
- Retorno total: **+258.28%**
- Max drawdown: **-13.84%**
- Trades en drawdown: **433/570 (76.0%)**

## Distribucion de R (sin costos)

- **n**: 570
- **mean**: 0.231
- **median**: 0.162
- **std**: 1.213
- **min**: -1.0
- **max**: 4.65
- **q05**: -1.0
- **q25**: -1.0
- **q75**: 1.15
- **q95**: 2.375
- **skew**: 0.646
- **kurtosis**: -0.261
- **winning_trades**: 301
- **losing_trades**: 269
- **expectancy**: 0.231
- **win_rate_pct**: 52.81

## Distribucion de R (con costos)

- Expectancy original: **0.231R**
- Expectancy con costos: **0.192R**
- Degradacion por costos: **-0.039R/trade**

## Distribucion por bucket de R

| bucket     |   n |   pct |
|:-----------|----:|------:|
| < -1.5R    |   0 |   0   |
| -1.5 a -1R | 218 |  38.2 |
| -1 a -0.5R |   7 |   1.2 |
| -0.5 a 0R  |  44 |   7.7 |
| 0 a 0.5R   |  58 |  10.2 |
| 0.5 a 1R   |  64 |  11.2 |
| 1 a 1.5R   |  99 |  17.4 |
| 1.5 a 2R   |  32 |   5.6 |
| 2 a 3R     |  37 |   6.5 |
| 3 a 5R     |  11 |   1.9 |
| > 5R       |   0 |   0   |

## Monte Carlo (2000 simulaciones)

- Capital final mediano: **$35,966.61**
- Capital final p05 (peor 5%): **$22,317.97**
- Capital final p95 (mejor 5%): **$57,551.34**
- Drawdown mediano: **-10.56%**
- Drawdown p95 (peor caso): **-16.91%**
- Mediana de prob. de ganar dinero: **100.0%**
- Max losses consecutivas (p95): **11**
- Max losses consecutivas peor caso: **20**

## Rolling Metrics (ventana=30 trades)

- Sharpe rolling promedio: **0.178**
- Sharpe rolling min: **-0.374**
- Sharpe rolling max: **0.634**
- Mean R primera mitad: **0.234R**
- Mean R segunda mitad: **0.216R**
- Edge degradation: **-0.018R**

## Time Exposure

- **n_trades**: 570
- **avg_bars_per_trade**: 9.94

## Veredicto cuantitativo

✅ **Sistema con edge robusto** — preserva expectancy bajo costos

🟢 **Edge estable** — sin degradacion notable entre periodos
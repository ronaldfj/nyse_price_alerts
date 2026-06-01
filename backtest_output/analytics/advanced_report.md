# Advanced Analytics Report

- Archivo: `backtest_output/backtest_trades.csv`
- Trades cerrados: **251**
- Capital inicial: **$10,000**
- Riesgo por trade: **1.0%**
- Comision: **$1.0** | Slippage: **0.05%** por lado

## Equity Curve (con compounding)

- Capital final: **$18,903.68**
- Retorno total: **+89.04%**
- Max drawdown: **-13.34%**
- Trades en drawdown: **206/251 (82.1%)**

## Distribucion de R (sin costos)

- **n**: 251
- **mean**: 0.265
- **median**: -0.378
- **std**: 1.46
- **min**: -1.0
- **max**: 5.338
- **q05**: -1.0
- **q25**: -1.0
- **q75**: 1.465
- **q95**: 2.732
- **skew**: 0.851
- **kurtosis**: -0.208
- **winning_trades**: 115
- **losing_trades**: 136
- **expectancy**: 0.265
- **win_rate_pct**: 45.82

## Distribucion de R (con costos)

- Expectancy original: **0.265R**
- Expectancy con costos: **0.211R**
- Degradacion por costos: **-0.054R/trade**

## Distribucion por bucket de R

| bucket     |   n |   pct |
|:-----------|----:|------:|
| < -1.5R    |   0 |   0   |
| -1.5 a -1R | 117 |  46.6 |
| -1 a -0.5R |   2 |   0.8 |
| -0.5 a 0R  |  17 |   6.8 |
| 0 a 0.5R   |  17 |   6.8 |
| 0.5 a 1R   |  17 |   6.8 |
| 1 a 1.5R   |  22 |   8.8 |
| 1.5 a 2R   |  19 |   7.6 |
| 2 a 3R     |  31 |  12.4 |
| 3 a 5R     |   8 |   3.2 |
| > 5R       |   1 |   0.4 |

## Monte Carlo (2000 simulaciones)

- Capital final mediano: **$19,024.07**
- Capital final p05 (peor 5%): **$13,057.52**
- Capital final p95 (mejor 5%): **$27,648.13**
- Drawdown mediano: **-10.43%**
- Drawdown p95 (peor caso): **-18.16%**
- Mediana de prob. de ganar dinero: **99.9%**
- Max losses consecutivas (p95): **12**
- Max losses consecutivas peor caso: **20**

## Rolling Metrics (ventana=30 trades)

- Sharpe rolling promedio: **0.151**
- Sharpe rolling min: **-0.415**
- Sharpe rolling max: **0.493**
- Mean R primera mitad: **0.244R**
- Mean R segunda mitad: **0.223R**
- Edge degradation: **-0.021R**

## Time Exposure

- **n_trades**: 251
- **avg_bars_per_trade**: 8.95

## Veredicto cuantitativo

✅ **Sistema con edge robusto** — preserva expectancy bajo costos

🟢 **Edge estable** — sin degradacion notable entre periodos
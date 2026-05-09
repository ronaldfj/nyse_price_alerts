# Advanced Analytics Report

- Archivo: `backtest_output/backtest_trades.csv`
- Trades cerrados: **255**
- Capital inicial: **$10,000**
- Riesgo por trade: **1.0%**
- Comision: **$1.0** | Slippage: **0.05%** por lado

## Equity Curve (con compounding)

- Capital final: **$22,118.80**
- Retorno total: **+121.19%**
- Max drawdown: **-10.98%**
- Trades en drawdown: **199/255 (78.0%)**

## Distribucion de R (sin costos)

- **n**: 255
- **mean**: 0.323
- **median**: -0.189
- **std**: 1.488
- **min**: -1.0
- **max**: 5.338
- **q05**: -1.0
- **q25**: -1.0
- **q75**: 1.546
- **q95**: 2.972
- **skew**: 0.781
- **kurtosis**: -0.398
- **winning_trades**: 121
- **losing_trades**: 134
- **expectancy**: 0.323
- **win_rate_pct**: 47.45

## Distribucion de R (con costos)

- Expectancy original: **0.323R**
- Expectancy con costos: **0.27R**
- Degradacion por costos: **-0.053R/trade**

## Distribucion por bucket de R

| bucket     |   n |   pct |
|:-----------|----:|------:|
| < -1.5R    |   0 |   0   |
| -1.5 a -1R | 115 |  45.1 |
| -1 a -0.5R |   3 |   1.2 |
| -0.5 a 0R  |  16 |   6.3 |
| 0 a 0.5R   |  17 |   6.7 |
| 0.5 a 1R   |  18 |   7.1 |
| 1 a 1.5R   |  21 |   8.2 |
| 1.5 a 2R   |  20 |   7.8 |
| 2 a 3R     |  33 |  12.9 |
| 3 a 5R     |  11 |   4.3 |
| > 5R       |   1 |   0.4 |

## Monte Carlo (2000 simulaciones)

- Capital final mediano: **$22,019.53**
- Capital final p05 (peor 5%): **$14,988.89**
- Capital final p95 (mejor 5%): **$32,825.22**
- Drawdown mediano: **-9.57%**
- Drawdown p95 (peor caso): **-15.90%**
- Mediana de prob. de ganar dinero: **100.0%**
- Max losses consecutivas (p95): **11**
- Max losses consecutivas peor caso: **20**

## Rolling Metrics (ventana=30 trades)

- Sharpe rolling promedio: **0.199**
- Sharpe rolling min: **-0.312**
- Sharpe rolling max: **0.613**
- Mean R primera mitad: **0.365R**
- Mean R segunda mitad: **0.246R**
- Edge degradation: **-0.118R**

## Time Exposure

- **n_trades**: 255
- **avg_bars_per_trade**: 8.94

## Veredicto cuantitativo

✅ **Sistema con edge robusto** — preserva expectancy bajo costos

⚠️ **Edge degradandose** — segunda mitad rinde menos que la primera (posible overfitting)
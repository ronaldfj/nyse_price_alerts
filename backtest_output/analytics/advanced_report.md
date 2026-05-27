# Advanced Analytics Report

- Archivo: `backtest_output/backtest_trades.csv`
- Trades cerrados: **254**
- Capital inicial: **$10,000**
- Riesgo por trade: **1.0%**
- Comision: **$1.0** | Slippage: **0.05%** por lado

## Equity Curve (con compounding)

- Capital final: **$19,625.58**
- Retorno total: **+96.26%**
- Max drawdown: **-12.44%**
- Trades en drawdown: **207/254 (81.5%)**

## Distribucion de R (sin costos)

- **n**: 254
- **mean**: 0.276
- **median**: -0.303
- **std**: 1.465
- **min**: -1.0
- **max**: 5.338
- **q05**: -1.0
- **q25**: -1.0
- **q75**: 1.479
- **q95**: 2.692
- **skew**: 0.827
- **kurtosis**: -0.277
- **winning_trades**: 117
- **losing_trades**: 137
- **expectancy**: 0.276
- **win_rate_pct**: 46.06

## Distribucion de R (con costos)

- Expectancy original: **0.276R**
- Expectancy con costos: **0.224R**
- Degradacion por costos: **-0.052R/trade**

## Distribucion por bucket de R

| bucket     |   n |   pct |
|:-----------|----:|------:|
| < -1.5R    |   0 |   0   |
| -1.5 a -1R | 118 |  46.5 |
| -1 a -0.5R |   2 |   0.8 |
| -0.5 a 0R  |  17 |   6.7 |
| 0 a 0.5R   |  17 |   6.7 |
| 0.5 a 1R   |  17 |   6.7 |
| 1 a 1.5R   |  21 |   8.3 |
| 1.5 a 2R   |  20 |   7.9 |
| 2 a 3R     |  33 |  13   |
| 3 a 5R     |   8 |   3.1 |
| > 5R       |   1 |   0.4 |

## Monte Carlo (2000 simulaciones)

- Capital final mediano: **$19,476.98**
- Capital final p05 (peor 5%): **$13,507.17**
- Capital final p95 (mejor 5%): **$28,805.11**
- Drawdown mediano: **-10.13%**
- Drawdown p95 (peor caso): **-17.53%**
- Mediana de prob. de ganar dinero: **99.7%**
- Max losses consecutivas (p95): **12**
- Max losses consecutivas peor caso: **20**

## Rolling Metrics (ventana=30 trades)

- Sharpe rolling promedio: **0.161**
- Sharpe rolling min: **-0.319**
- Sharpe rolling max: **0.495**
- Mean R primera mitad: **0.283R**
- Mean R segunda mitad: **0.215R**
- Edge degradation: **-0.069R**

## Time Exposure

- **n_trades**: 254
- **avg_bars_per_trade**: 8.94

## Veredicto cuantitativo

✅ **Sistema con edge robusto** — preserva expectancy bajo costos

🟢 **Edge estable** — sin degradacion notable entre periodos
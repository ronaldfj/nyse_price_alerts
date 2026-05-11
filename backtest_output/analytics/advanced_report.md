# Advanced Analytics Report

- Archivo: `backtest_output/backtest_trades.csv`
- Trades cerrados: **254**
- Capital inicial: **$10,000**
- Riesgo por trade: **1.0%**
- Comision: **$1.0** | Slippage: **0.05%** por lado

## Equity Curve (con compounding)

- Capital final: **$21,089.94**
- Retorno total: **+110.90%**
- Max drawdown: **-9.72%**
- Trades en drawdown: **200/254 (78.7%)**

## Distribucion de R (sin costos)

- **n**: 254
- **mean**: 0.305
- **median**: -0.21
- **std**: 1.484
- **min**: -1.0
- **max**: 5.338
- **q05**: -1.0
- **q25**: -1.0
- **q75**: 1.488
- **q95**: 2.974
- **skew**: 0.807
- **kurtosis**: -0.35
- **winning_trades**: 119
- **losing_trades**: 135
- **expectancy**: 0.305
- **win_rate_pct**: 46.85

## Distribucion de R (con costos)

- Expectancy original: **0.305R**
- Expectancy con costos: **0.252R**
- Degradacion por costos: **-0.053R/trade**

## Distribucion por bucket de R

| bucket     |   n |   pct |
|:-----------|----:|------:|
| < -1.5R    |   0 |   0   |
| -1.5 a -1R | 116 |  45.7 |
| -1 a -0.5R |   2 |   0.8 |
| -0.5 a 0R  |  17 |   6.7 |
| 0 a 0.5R   |  17 |   6.7 |
| 0.5 a 1R   |  18 |   7.1 |
| 1 a 1.5R   |  21 |   8.3 |
| 1.5 a 2R   |  19 |   7.5 |
| 2 a 3R     |  32 |  12.6 |
| 3 a 5R     |  11 |   4.3 |
| > 5R       |   1 |   0.4 |

## Monte Carlo (2000 simulaciones)

- Capital final mediano: **$20,890.40**
- Capital final p05 (peor 5%): **$14,482.97**
- Capital final p95 (mejor 5%): **$31,133.12**
- Drawdown mediano: **-9.79%**
- Drawdown p95 (peor caso): **-16.39%**
- Mediana de prob. de ganar dinero: **100.0%**
- Max losses consecutivas (p95): **12**
- Max losses consecutivas peor caso: **19**

## Rolling Metrics (ventana=30 trades)

- Sharpe rolling promedio: **0.190**
- Sharpe rolling min: **-0.244**
- Sharpe rolling max: **0.504**
- Mean R primera mitad: **0.332R**
- Mean R segunda mitad: **0.248R**
- Edge degradation: **-0.084R**

## Time Exposure

- **n_trades**: 254
- **avg_bars_per_trade**: 8.93

## Veredicto cuantitativo

✅ **Sistema con edge robusto** — preserva expectancy bajo costos

🟢 **Edge estable** — sin degradacion notable entre periodos
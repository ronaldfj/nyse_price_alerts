# Advanced Analytics Report

- Archivo: `backtest_output/backtest_trades.csv`
- Trades cerrados: **270**
- Capital inicial: **$10,000**
- Riesgo por trade: **1.0%**
- Comision: **$1.0** | Slippage: **0.05%** por lado

## Equity Curve (con compounding)

- Capital final: **$21,854.59**
- Retorno total: **+118.55%**
- Max drawdown: **-11.60%**
- Trades en drawdown: **214/270 (79.3%)**

## Distribucion de R (sin costos)

- **n**: 270
- **mean**: 0.3
- **median**: -0.19
- **std**: 1.459
- **min**: -1.0
- **max**: 5.338
- **q05**: -1.0
- **q25**: -1.0
- **q75**: 1.46
- **q95**: 2.897
- **skew**: 0.812
- **kurtosis**: -0.289
- **winning_trades**: 127
- **losing_trades**: 143
- **expectancy**: 0.3
- **win_rate_pct**: 47.04

## Distribucion de R (con costos)

- Expectancy original: **0.3R**
- Expectancy con costos: **0.249R**
- Degradacion por costos: **-0.051R/trade**

## Distribucion por bucket de R

| bucket     |   n |   pct |
|:-----------|----:|------:|
| < -1.5R    |   0 |   0   |
| -1.5 a -1R | 119 |  44.1 |
| -1 a -0.5R |   5 |   1.9 |
| -0.5 a 0R  |  19 |   7   |
| 0 a 0.5R   |  18 |   6.7 |
| 0.5 a 1R   |  19 |   7   |
| 1 a 1.5R   |  26 |   9.6 |
| 1.5 a 2R   |  19 |   7   |
| 2 a 3R     |  33 |  12.2 |
| 3 a 5R     |  11 |   4.1 |
| > 5R       |   1 |   0.4 |

## Monte Carlo (2000 simulaciones)

- Capital final mediano: **$21,869.40**
- Capital final p05 (peor 5%): **$14,967.47**
- Capital final p95 (mejor 5%): **$32,415.43**
- Drawdown mediano: **-9.70%**
- Drawdown p95 (peor caso): **-16.25%**
- Mediana de prob. de ganar dinero: **100.0%**
- Max losses consecutivas (p95): **11**
- Max losses consecutivas peor caso: **19**

## Rolling Metrics (ventana=30 trades)

- Sharpe rolling promedio: **0.189**
- Sharpe rolling min: **-0.347**
- Sharpe rolling max: **0.513**
- Mean R primera mitad: **0.329R**
- Mean R segunda mitad: **0.246R**
- Edge degradation: **-0.083R**

## Time Exposure

- **n_trades**: 270
- **avg_bars_per_trade**: 8.92

## Veredicto cuantitativo

✅ **Sistema con edge robusto** — preserva expectancy bajo costos

🟢 **Edge estable** — sin degradacion notable entre periodos
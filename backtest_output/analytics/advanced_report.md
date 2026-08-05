# Advanced Analytics Report

- Archivo: `backtest_output/backtest_trades.csv`
- Trades cerrados: **144**
- Capital inicial: **$10,000**
- Riesgo por trade: **1.0%**
- Comision: **$1.0** | Slippage: **0.05%** por lado

## Equity Curve (con compounding)

- Capital final: **$18,693.49**
- Retorno total: **+86.93%**
- Max drawdown: **-6.46%**
- Trades en drawdown: **105/144 (72.9%)**

## Distribucion de R (sin costos)

- **n**: 144
- **mean**: 0.459
- **median**: -0.108
- **std**: 2.281
- **min**: -1.0
- **max**: 21.058
- **q05**: -1.0
- **q25**: -1.0
- **q75**: 1.257
- **q95**: 2.854
- **skew**: 5.474
- **kurtosis**: 46.223
- **winning_trades**: 70
- **losing_trades**: 74
- **expectancy**: 0.459
- **win_rate_pct**: 48.61

## Distribucion de R (con costos)

- Expectancy original: **0.459R**
- Expectancy con costos: **0.391R**
- Degradacion por costos: **-0.068R/trade**

## Distribucion por bucket de R

| bucket     |   n |   pct |
|:-----------|----:|------:|
| < -1.5R    |   0 |   0   |
| -1.5 a -1R |   2 |   1.4 |
| -1 a -0.5R |  61 |  42.4 |
| -0.5 a 0R  |  11 |   7.6 |
| 0 a 0.5R   |   7 |   4.9 |
| 0.5 a 1R   |  14 |   9.7 |
| 1 a 1.5R   |  21 |  14.6 |
| 1.5 a 2R   |  12 |   8.3 |
| 2 a 3R     |   9 |   6.2 |
| 3 a 5R     |   4 |   2.8 |
| > 5R       |   3 |   2.1 |

## Monte Carlo (2000 simulaciones)

- Capital final mediano: **$18,519.75**
- Capital final p05 (peor 5%): **$12,821.46**
- Capital final p95 (mejor 5%): **$29,500.25**
- Drawdown mediano: **-7.65%**
- Drawdown p95 (peor caso): **-13.10%**
- Mediana de prob. de ganar dinero: **99.8%**
- Max losses consecutivas (p95): **10**
- Max losses consecutivas peor caso: **19**

## Rolling Metrics (ventana=30 trades)

- Sharpe rolling promedio: **0.225**
- Sharpe rolling min: **-0.024**
- Sharpe rolling max: **0.478**
- Mean R primera mitad: **0.356R**
- Mean R segunda mitad: **0.378R**
- Edge degradation: **+0.022R**

## Time Exposure

- **n_trades**: 144
- **avg_bars_per_trade**: 8.9

## Veredicto cuantitativo

✅ **Sistema con edge robusto** — preserva expectancy bajo costos

🟢 **Edge estable** — sin degradacion notable entre periodos
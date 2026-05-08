# Advanced Analytics Report

- Archivo: `backtest_output/backtest_trades.csv`
- Trades cerrados: **307**
- Capital inicial: **$10,000**
- Riesgo por trade: **1.0%**
- Comision: **$1.0** | Slippage: **0.05%** por lado

## Equity Curve (con compounding)

- Capital final: **$25,354.46**
- Retorno total: **+153.54%**
- Max drawdown: **-13.14%**
- Trades en drawdown: **236/307 (76.9%)**

## Distribucion de R (sin costos)

- **n**: 307
- **mean**: 0.314
- **median**: -0.183
- **std**: 1.437
- **min**: -1.0
- **max**: 4.65
- **q05**: -1.0
- **q25**: -1.0
- **q75**: 1.466
- **q95**: 2.672
- **skew**: 0.628
- **kurtosis**: -0.798
- **winning_trades**: 149
- **losing_trades**: 158
- **expectancy**: 0.314
- **win_rate_pct**: 48.53

## Distribucion de R (con costos)

- Expectancy original: **0.314R**
- Expectancy con costos: **0.268R**
- Degradacion por costos: **-0.046R/trade**

## Distribucion por bucket de R

| bucket     |   n |   pct |
|:-----------|----:|------:|
| < -1.5R    |   0 |   0   |
| -1.5 a -1R | 141 |  45.9 |
| -1 a -0.5R |   4 |   1.3 |
| -0.5 a 0R  |  13 |   4.2 |
| 0 a 0.5R   |  15 |   4.9 |
| 0.5 a 1R   |  22 |   7.2 |
| 1 a 1.5R   |  38 |  12.4 |
| 1.5 a 2R   |  24 |   7.8 |
| 2 a 3R     |  40 |  13   |
| 3 a 5R     |  10 |   3.3 |
| > 5R       |   0 |   0   |

## Monte Carlo (2000 simulaciones)

- Capital final mediano: **$25,220.01**
- Capital final p05 (peor 5%): **$16,617.61**
- Capital final p95 (mejor 5%): **$38,614.37**
- Drawdown mediano: **-9.80%**
- Drawdown p95 (peor caso): **-16.16%**
- Mediana de prob. de ganar dinero: **100.0%**
- Max losses consecutivas (p95): **11**
- Max losses consecutivas peor caso: **18**

## Rolling Metrics (ventana=30 trades)

- Sharpe rolling promedio: **0.208**
- Sharpe rolling min: **-0.344**
- Sharpe rolling max: **0.446**
- Mean R primera mitad: **0.291R**
- Mean R segunda mitad: **0.332R**
- Edge degradation: **+0.041R**

## Time Exposure

- **n_trades**: 307
- **avg_bars_per_trade**: 8.89

## Veredicto cuantitativo

✅ **Sistema con edge robusto** — preserva expectancy bajo costos

🟢 **Edge estable** — sin degradacion notable entre periodos
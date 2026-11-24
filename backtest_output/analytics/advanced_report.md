# Advanced Analytics Report

- Archivo: `backtest_output/backtest_trades.csv`
- Trades cerrados: **151**
- Capital inicial: **$10,000**
- Riesgo por trade: **1.0%**
- Comision: **$1.0** | Slippage: **0.05%** por lado

## Equity Curve (con compounding)

- Capital final: **$15,527.96**
- Retorno total: **+55.28%**
- Max drawdown: **-13.50%**
- Trades en drawdown: **117/151 (77.5%)**

## Distribucion de R (sin costos)

- **n**: 151
- **mean**: 0.302
- **median**: -0.236
- **std**: 1.469
- **min**: -1.593
- **max**: 4.67
- **q05**: -1.09
- **q25**: -1.0
- **q75**: 1.492
- **q95**: 2.831
- **skew**: 0.71
- **kurtosis**: -0.514
- **winning_trades**: 69
- **losing_trades**: 82
- **expectancy**: 0.302
- **win_rate_pct**: 45.7

## Distribucion de R (con costos)

- Expectancy original: **0.302R**
- Expectancy con costos: **0.26R**
- Degradacion por costos: **-0.042R/trade**

## Distribucion por bucket de R

| bucket     |   n |   pct |
|:-----------|----:|------:|
| < -1.5R    |   1 |   0.7 |
| -1.5 a -1R |  11 |   7.3 |
| -1 a -0.5R |  57 |  37.7 |
| -0.5 a 0R  |  13 |   8.6 |
| 0 a 0.5R   |   5 |   3.3 |
| 0.5 a 1R   |   6 |   4   |
| 1 a 1.5R   |  20 |  13.2 |
| 1.5 a 2R   |  17 |  11.3 |
| 2 a 3R     |  14 |   9.3 |
| 3 a 5R     |   7 |   4.6 |
| > 5R       |   0 |   0   |

## Monte Carlo (2000 simulaciones)

- Capital final mediano: **$15,534.20**
- Capital final p05 (peor 5%): **$11,541.26**
- Capital final p95 (mejor 5%): **$20,915.70**
- Drawdown mediano: **-8.39%**
- Drawdown p95 (peor caso): **-14.78%**
- Mediana de prob. de ganar dinero: **99.2%**
- Max losses consecutivas (p95): **11**
- Max losses consecutivas peor caso: **18**

## Rolling Metrics (ventana=30 trades)

- Sharpe rolling promedio: **0.180**
- Sharpe rolling min: **-0.196**
- Sharpe rolling max: **0.634**
- Mean R primera mitad: **0.026R**
- Mean R segunda mitad: **0.529R**
- Edge degradation: **+0.504R**

## Time Exposure

- **n_trades**: 151
- **total_days**: 1073
- **avg_bars_per_trade**: 10.44
- **median_bars**: 9.0
- **max_bars**: 20
- **time_in_market_pct**: 100.0

## Veredicto cuantitativo

✅ **Sistema con edge robusto** — preserva expectancy bajo costos

✅ **Edge fortaleciendose** — segunda mitad rinde mas que la primera
# Comparacion de Playbooks — Fase B

- Capital inicial: **$10,000**
- Riesgo por trade: **1.0%**
- Costos: comision **$1.0** + slippage **0.05%/lado**
- Monte Carlo: **2000** runs (bootstrap)

## Comparacion head-to-head

| playbook   |   n |   win_rate_pct |   expectancy |   expectancy_with_costs |   max_drawdown_pct |   mc_worst_drawdown |   mc_prob_profit_pct |   rolling_sharpe_avg |   edge_degradation |
|:-----------|----:|---------------:|-------------:|------------------------:|-------------------:|--------------------:|---------------------:|---------------------:|-------------------:|
| all        | 570 |          52.81 |        0.231 |                   0.192 |             -13.84 |              -16.91 |               100    |                0.178 |             -0.018 |
| breakout   | 235 |          48.94 |        0.365 |                   0.319 |             -13.68 |              -14.36 |                99.95 |                0.222 |              0.105 |
| pullback   | 320 |          56.88 |        0.154 |                   0.121 |             -12.73 |              -13.84 |                99.7  |                0.157 |             -0.138 |
| hybrid     |  15 |          26.67 |       -0.208 |                  -0.261 |              -7.03 |              -11.59 |                24.75 |               -0.332 |              0.208 |

## Distribucion de R

| playbook   |   n |   median_r |   std_r |   skew |   min_r |   p05_r |   p95_r |   max_r |
|:-----------|----:|-----------:|--------:|-------:|--------:|--------:|--------:|--------:|
| all        | 570 |      0.162 |   1.213 |  0.646 |      -1 |      -1 |   2.375 |   4.65  |
| breakout   | 235 |     -0.115 |   1.504 |  0.632 |      -1 |      -1 |   2.963 |   4.65  |
| pullback   | 320 |      0.286 |   0.924 |  0.011 |      -1 |      -1 |   1.372 |   3.07  |
| hybrid     |  15 |     -1     |   1.373 |  1.251 |      -1 |      -1 |   2.104 |   2.555 |

## Equity Curve + Monte Carlo

| playbook   |   final_capital |   total_return_pct |   mc_median_capital |   mc_p05_capital |   mc_p95_capital |   mc_median_drawdown |   mc_max_consec_losses_p95 |
|:-----------|----------------:|-------------------:|--------------------:|-----------------:|-----------------:|---------------------:|---------------------------:|
| all        |        35828.4  |             258.28 |            35966.6  |         22318    |          57551.4 |               -10.56 |                         11 |
| breakout   |        22918    |             129.18 |            22996    |         15807.5  |          33283.5 |                -8.7  |                         11 |
| pullback   |        16149.6  |              61.5  |            16244.4  |         12516    |          21595.7 |                -8.21 |                          9 |
| hybrid     |         9680.29 |              -3.2  |             9668.87 |          8853.39 |          10530.3 |                -6.31 |                         11 |

## Veredicto comparativo

- **Mejor expectancy con costos**: `breakout` (0.319R, n=235)
- **Mejor Sharpe rolling**: `breakout` (0.222)
- **Menor drawdown**: `hybrid` (-7.03%)

### breakout
- ✅ edge robusto
- Expectancy con costos: **0.319R**
- Sharpe rolling: **0.222**
- Trades: **235**
- Max losses consecutivas (MC p95): **11**

### pullback
- 🟡 edge modesto | ⚠️ edge degradandose
- Expectancy con costos: **0.121R**
- Sharpe rolling: **0.157**
- Trades: **320**
- Max losses consecutivas (MC p95): **9**

### hybrid
- ⛔ NO rentable con costos
- Expectancy con costos: **-0.261R**
- Sharpe rolling: **-0.332**
- Trades: **15**
- Max losses consecutivas (MC p95): **11**

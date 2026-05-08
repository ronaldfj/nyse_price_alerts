# Comparacion de Playbooks — Fase B

- Capital inicial: **$10,000**
- Riesgo por trade: **1.0%**
- Costos: comision **$1.0** + slippage **0.05%/lado**
- Monte Carlo: **2000** runs (bootstrap)

## Comparacion head-to-head

| playbook   |   n |   win_rate_pct |   expectancy |   expectancy_with_costs |   max_drawdown_pct |   mc_worst_drawdown |   mc_prob_profit_pct |   rolling_sharpe_avg |   edge_degradation |
|:-----------|----:|---------------:|-------------:|------------------------:|-------------------:|--------------------:|---------------------:|---------------------:|-------------------:|
| all        | 305 |          46.89 |        0.283 |                   0.236 |             -14.44 |              -18.05 |                99.95 |                0.175 |              0.106 |
| breakout   | 287 |          48.08 |        0.316 |                   0.27  |             -13.58 |              -15.96 |               100    |                0.199 |              0.048 |
| pullback   |   0 |         nan    |      nan     |                 nan     |             nan    |              nan    |               nan    |              nan     |            nan     |
| hybrid     |  18 |          27.78 |       -0.255 |                  -0.311 |              -7.96 |              -13.13 |                18.3  |               -0.334 |              0.29  |

## Distribucion de R

| playbook   |   n |   median_r |   std_r |    skew |   min_r |   p05_r |   p95_r |   max_r |
|:-----------|----:|-----------:|--------:|--------:|--------:|--------:|--------:|--------:|
| all        | 305 |     -0.456 |   1.458 |   0.663 |      -1 |      -1 |   2.675 |   4.65  |
| breakout   | 287 |     -0.275 |   1.464 |   0.634 |      -1 |      -1 |   2.743 |   4.65  |
| pullback   |   0 |    nan     | nan     | nan     |     nan |     nan | nan     | nan     |
| hybrid     |  18 |     -1     |   1.286 |   1.327 |      -1 |      -1 |   2.007 |   2.555 |

## Equity Curve + Monte Carlo

| playbook   |   final_capital |   total_return_pct |   mc_median_capital |   mc_p05_capital |   mc_p95_capital |   mc_median_drawdown |   mc_max_consec_losses_p95 |
|:-----------|----------------:|-------------------:|--------------------:|-----------------:|-----------------:|---------------------:|---------------------------:|
| all        |        22909.8  |             129.1  |            22690.5  |         15070.1  |          34003.1 |               -10.71 |                         12 |
| breakout   |        24022    |             140.22 |            24251.1  |         16027.1  |          35616.3 |                -9.91 |                         12 |
| pullback   |          nan    |             nan    |              nan    |           nan    |            nan   |               nan    |                        nan |
| hybrid     |         9537.02 |              -4.63 |             9513.51 |          8777.57 |          10442.7 |                -7.69 |                         12 |

## Veredicto comparativo

- **Mejor expectancy con costos**: `breakout` (0.270R, n=287)
- **Mejor Sharpe rolling**: `breakout` (0.199)
- **Menor drawdown**: `hybrid` (-7.96%)

### breakout
- ✅ edge robusto | 🟢 edge estable
- Expectancy con costos: **0.270R**
- Sharpe rolling: **0.199**
- Trades: **287**
- Max losses consecutivas (MC p95): **12**

### hybrid
- ⛔ NO rentable con costos
- Expectancy con costos: **-0.311R**
- Sharpe rolling: **-0.334**
- Trades: **18**
- Max losses consecutivas (MC p95): **12**

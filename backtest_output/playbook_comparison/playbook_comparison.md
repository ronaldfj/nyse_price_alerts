# Comparacion de Playbooks — Fase B

- Capital inicial: **$10,000**
- Riesgo por trade: **1.0%**
- Costos: comision **$1.0** + slippage **0.05%/lado**
- Monte Carlo: **2000** runs (bootstrap)

## Comparacion head-to-head

| playbook   |   n |   win_rate_pct |   expectancy |   expectancy_with_costs |   max_drawdown_pct |   mc_worst_drawdown |   mc_prob_profit_pct |   rolling_sharpe_avg |   edge_degradation |
|:-----------|----:|---------------:|-------------:|------------------------:|-------------------:|--------------------:|---------------------:|---------------------:|-------------------:|
| all        | 139 |           48.2 |        0.364 |                   0.321 |             -14.36 |              -15.09 |                 99.6 |                0.207 |               0.49 |
| breakout   | 139 |           48.2 |        0.364 |                   0.321 |             -14.36 |              -15.09 |                 99.6 |                0.207 |               0.49 |
| pullback   |   0 |          nan   |      nan     |                 nan     |             nan    |              nan    |                nan   |              nan     |             nan    |
| hybrid     |   0 |          nan   |      nan     |                 nan     |             nan    |              nan    |                nan   |              nan     |             nan    |

## Distribucion de R

| playbook   |   n |   median_r |   std_r |    skew |   min_r |   p05_r |   p95_r |   max_r |
|:-----------|----:|-----------:|--------:|--------:|--------:|--------:|--------:|--------:|
| all        | 139 |     -0.184 |   1.573 |   0.388 |  -4.124 |  -1.094 |   2.933 |    4.67 |
| breakout   | 139 |     -0.184 |   1.573 |   0.388 |  -4.124 |  -1.094 |   2.933 |    4.67 |
| pullback   |   0 |    nan     | nan     | nan     | nan     | nan     | nan     |  nan    |
| hybrid     |   0 |    nan     | nan     | nan     | nan     | nan     | nan     |  nan    |

## Equity Curve + Monte Carlo

| playbook   |   final_capital |   total_return_pct |   mc_median_capital |   mc_p05_capital |   mc_p95_capital |   mc_median_drawdown |   mc_max_consec_losses_p95 |
|:-----------|----------------:|-------------------:|--------------------:|-----------------:|-----------------:|---------------------:|---------------------------:|
| all        |           16285 |              62.85 |             16120.2 |          12077.6 |          21955.9 |                -8.63 |                         10 |
| breakout   |           16285 |              62.85 |             16120.2 |          12077.6 |          21955.9 |                -8.63 |                         10 |
| pullback   |             nan |             nan    |               nan   |            nan   |            nan   |               nan    |                        nan |
| hybrid     |             nan |             nan    |               nan   |            nan   |            nan   |               nan    |                        nan |

## Veredicto comparativo

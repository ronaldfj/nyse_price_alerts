# Comparacion de Playbooks — Fase B

- Capital inicial: **$10,000**
- Riesgo por trade: **1.0%**
- Costos: comision **$1.0** + slippage **0.05%/lado**
- Monte Carlo: **2000** runs (bootstrap)

## Comparacion head-to-head

| playbook   |   n |   win_rate_pct |   expectancy |   expectancy_with_costs |   max_drawdown_pct |   mc_worst_drawdown |   mc_prob_profit_pct |   rolling_sharpe_avg |   edge_degradation |
|:-----------|----:|---------------:|-------------:|------------------------:|-------------------:|--------------------:|---------------------:|---------------------:|-------------------:|
| all        | 251 |          45.82 |        0.265 |                   0.211 |             -13.34 |              -18.16 |                99.85 |                0.151 |             -0.021 |
| breakout   | 251 |          45.82 |        0.265 |                   0.211 |             -13.34 |              -18.16 |                99.85 |                0.151 |             -0.021 |
| pullback   |   0 |         nan    |      nan     |                 nan     |             nan    |              nan    |               nan    |              nan     |            nan     |
| hybrid     |   0 |         nan    |      nan     |                 nan     |             nan    |              nan    |               nan    |              nan     |            nan     |

## Distribucion de R

| playbook   |   n |   median_r |   std_r |    skew |   min_r |   p05_r |   p95_r |   max_r |
|:-----------|----:|-----------:|--------:|--------:|--------:|--------:|--------:|--------:|
| all        | 251 |     -0.378 |    1.46 |   0.851 |      -1 |      -1 |   2.732 |   5.338 |
| breakout   | 251 |     -0.378 |    1.46 |   0.851 |      -1 |      -1 |   2.732 |   5.338 |
| pullback   |   0 |    nan     |  nan    | nan     |     nan |     nan | nan     | nan     |
| hybrid     |   0 |    nan     |  nan    | nan     |     nan |     nan | nan     | nan     |

## Equity Curve + Monte Carlo

| playbook   |   final_capital |   total_return_pct |   mc_median_capital |   mc_p05_capital |   mc_p95_capital |   mc_median_drawdown |   mc_max_consec_losses_p95 |
|:-----------|----------------:|-------------------:|--------------------:|-----------------:|-----------------:|---------------------:|---------------------------:|
| all        |         18903.7 |              89.04 |             19024.1 |          13057.5 |          27648.1 |               -10.43 |                         12 |
| breakout   |         18903.7 |              89.04 |             19024.1 |          13057.5 |          27648.1 |               -10.43 |                         12 |
| pullback   |           nan   |             nan    |               nan   |            nan   |            nan   |               nan    |                        nan |
| hybrid     |           nan   |             nan    |               nan   |            nan   |            nan   |               nan    |                        nan |

## Veredicto comparativo

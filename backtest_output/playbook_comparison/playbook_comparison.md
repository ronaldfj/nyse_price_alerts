# Comparacion de Playbooks — Fase B

- Capital inicial: **$10,000**
- Riesgo por trade: **1.0%**
- Costos: comision **$1.0** + slippage **0.05%/lado**
- Monte Carlo: **2000** runs (bootstrap)

## Comparacion head-to-head

| playbook   |   n |   win_rate_pct |   expectancy |   expectancy_with_costs |   max_drawdown_pct |   mc_worst_drawdown |   mc_prob_profit_pct |   rolling_sharpe_avg |   edge_degradation |
|:-----------|----:|---------------:|-------------:|------------------------:|-------------------:|--------------------:|---------------------:|---------------------:|-------------------:|
| all        | 144 |          48.61 |        0.459 |                   0.391 |              -6.46 |               -13.1 |                 99.8 |                0.225 |              0.022 |
| breakout   | 144 |          48.61 |        0.459 |                   0.391 |              -6.46 |               -13.1 |                 99.8 |                0.225 |              0.022 |
| pullback   |   0 |         nan    |      nan     |                 nan     |             nan    |               nan   |                nan   |              nan     |            nan     |
| hybrid     |   0 |         nan    |      nan     |                 nan     |             nan    |               nan   |                nan   |              nan     |            nan     |

## Distribucion de R

| playbook   |   n |   median_r |   std_r |    skew |   min_r |   p05_r |   p95_r |   max_r |
|:-----------|----:|-----------:|--------:|--------:|--------:|--------:|--------:|--------:|
| all        | 144 |     -0.108 |   2.281 |   5.474 |      -1 |      -1 |   2.854 |  21.058 |
| breakout   | 144 |     -0.108 |   2.281 |   5.474 |      -1 |      -1 |   2.854 |  21.058 |
| pullback   |   0 |    nan     | nan     | nan     |     nan |     nan | nan     | nan     |
| hybrid     |   0 |    nan     | nan     | nan     |     nan |     nan | nan     | nan     |

## Equity Curve + Monte Carlo

| playbook   |   final_capital |   total_return_pct |   mc_median_capital |   mc_p05_capital |   mc_p95_capital |   mc_median_drawdown |   mc_max_consec_losses_p95 |
|:-----------|----------------:|-------------------:|--------------------:|-----------------:|-----------------:|---------------------:|---------------------------:|
| all        |         18693.5 |              86.93 |             18519.8 |          12821.5 |          29500.2 |                -7.65 |                         10 |
| breakout   |         18693.5 |              86.93 |             18519.8 |          12821.5 |          29500.2 |                -7.65 |                         10 |
| pullback   |           nan   |             nan    |               nan   |            nan   |            nan   |               nan    |                        nan |
| hybrid     |           nan   |             nan    |               nan   |            nan   |            nan   |               nan    |                        nan |

## Veredicto comparativo

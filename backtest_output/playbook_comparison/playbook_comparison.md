# Comparacion de Playbooks — Fase B

- Capital inicial: **$10,000**
- Riesgo por trade: **1.0%**
- Costos: comision **$1.0** + slippage **0.05%/lado**
- Monte Carlo: **2000** runs (bootstrap)

## Comparacion head-to-head

| playbook   |   n |   win_rate_pct |   expectancy |   expectancy_with_costs |   max_drawdown_pct |   mc_worst_drawdown |   mc_prob_profit_pct |   rolling_sharpe_avg |   edge_degradation |
|:-----------|----:|---------------:|-------------:|------------------------:|-------------------:|--------------------:|---------------------:|---------------------:|-------------------:|
| all        | 151 |           45.7 |        0.302 |                    0.26 |              -13.5 |              -14.78 |                99.15 |                 0.18 |              0.504 |
| breakout   | 151 |           45.7 |        0.302 |                    0.26 |              -13.5 |              -14.78 |                99.15 |                 0.18 |              0.504 |
| pullback   |   0 |          nan   |      nan     |                  nan    |              nan   |              nan    |               nan    |               nan    |            nan     |
| hybrid     |   0 |          nan   |      nan     |                  nan    |              nan   |              nan    |               nan    |               nan    |            nan     |

## Distribucion de R

| playbook   |   n |   median_r |   std_r |   skew |   min_r |   p05_r |   p95_r |   max_r |
|:-----------|----:|-----------:|--------:|-------:|--------:|--------:|--------:|--------:|
| all        | 151 |     -0.236 |   1.469 |   0.71 |  -1.593 |   -1.09 |   2.831 |    4.67 |
| breakout   | 151 |     -0.236 |   1.469 |   0.71 |  -1.593 |   -1.09 |   2.831 |    4.67 |
| pullback   |   0 |    nan     | nan     | nan    | nan     |  nan    | nan     |  nan    |
| hybrid     |   0 |    nan     | nan     | nan    | nan     |  nan    | nan     |  nan    |

## Equity Curve + Monte Carlo

| playbook   |   final_capital |   total_return_pct |   mc_median_capital |   mc_p05_capital |   mc_p95_capital |   mc_median_drawdown |   mc_max_consec_losses_p95 |
|:-----------|----------------:|-------------------:|--------------------:|-----------------:|-----------------:|---------------------:|---------------------------:|
| all        |           15528 |              55.28 |             15534.2 |          11541.3 |          20915.7 |                -8.39 |                         11 |
| breakout   |           15528 |              55.28 |             15534.2 |          11541.3 |          20915.7 |                -8.39 |                         11 |
| pullback   |             nan |             nan    |               nan   |            nan   |            nan   |               nan    |                        nan |
| hybrid     |             nan |             nan    |               nan   |            nan   |            nan   |               nan    |                        nan |

## Veredicto comparativo

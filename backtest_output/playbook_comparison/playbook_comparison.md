# Comparacion de Playbooks — Fase B

- Capital inicial: **$10,000**
- Riesgo por trade: **1.0%**
- Costos: comision **$1.0** + slippage **0.05%/lado**
- Monte Carlo: **2000** runs (bootstrap)

## Comparacion head-to-head

| playbook   |   n |   win_rate_pct |   expectancy |   expectancy_with_costs |   max_drawdown_pct |   mc_worst_drawdown |   mc_prob_profit_pct |   rolling_sharpe_avg |   edge_degradation |
|:-----------|----:|---------------:|-------------:|------------------------:|-------------------:|--------------------:|---------------------:|---------------------:|-------------------:|
| all        | 255 |          47.45 |        0.323 |                    0.27 |             -10.98 |               -15.9 |                  100 |                0.199 |             -0.118 |
| breakout   | 255 |          47.45 |        0.323 |                    0.27 |             -10.98 |               -15.9 |                  100 |                0.199 |             -0.118 |
| pullback   |   0 |         nan    |      nan     |                  nan    |             nan    |               nan   |                  nan |              nan     |            nan     |
| hybrid     |   0 |         nan    |      nan     |                  nan    |             nan    |               nan   |                  nan |              nan     |            nan     |

## Distribucion de R

| playbook   |   n |   median_r |   std_r |    skew |   min_r |   p05_r |   p95_r |   max_r |
|:-----------|----:|-----------:|--------:|--------:|--------:|--------:|--------:|--------:|
| all        | 255 |     -0.189 |   1.488 |   0.781 |      -1 |      -1 |   2.972 |   5.338 |
| breakout   | 255 |     -0.189 |   1.488 |   0.781 |      -1 |      -1 |   2.972 |   5.338 |
| pullback   |   0 |    nan     | nan     | nan     |     nan |     nan | nan     | nan     |
| hybrid     |   0 |    nan     | nan     | nan     |     nan |     nan | nan     | nan     |

## Equity Curve + Monte Carlo

| playbook   |   final_capital |   total_return_pct |   mc_median_capital |   mc_p05_capital |   mc_p95_capital |   mc_median_drawdown |   mc_max_consec_losses_p95 |
|:-----------|----------------:|-------------------:|--------------------:|-----------------:|-----------------:|---------------------:|---------------------------:|
| all        |         22118.8 |             121.19 |             22019.5 |          14988.9 |          32825.2 |                -9.57 |                         11 |
| breakout   |         22118.8 |             121.19 |             22019.5 |          14988.9 |          32825.2 |                -9.57 |                         11 |
| pullback   |           nan   |             nan    |               nan   |            nan   |            nan   |               nan    |                        nan |
| hybrid     |           nan   |             nan    |               nan   |            nan   |            nan   |               nan    |                        nan |

## Veredicto comparativo

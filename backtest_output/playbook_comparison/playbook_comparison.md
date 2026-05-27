# Comparacion de Playbooks — Fase B

- Capital inicial: **$10,000**
- Riesgo por trade: **1.0%**
- Costos: comision **$1.0** + slippage **0.05%/lado**
- Monte Carlo: **2000** runs (bootstrap)

## Comparacion head-to-head

| playbook   |   n |   win_rate_pct |   expectancy |   expectancy_with_costs |   max_drawdown_pct |   mc_worst_drawdown |   mc_prob_profit_pct |   rolling_sharpe_avg |   edge_degradation |
|:-----------|----:|---------------:|-------------:|------------------------:|-------------------:|--------------------:|---------------------:|---------------------:|-------------------:|
| all        | 254 |          46.06 |        0.276 |                   0.224 |             -12.44 |              -17.53 |                99.65 |                0.161 |             -0.069 |
| breakout   | 254 |          46.06 |        0.276 |                   0.224 |             -12.44 |              -17.53 |                99.65 |                0.161 |             -0.069 |
| pullback   |   0 |         nan    |      nan     |                 nan     |             nan    |              nan    |               nan    |              nan     |            nan     |
| hybrid     |   0 |         nan    |      nan     |                 nan     |             nan    |              nan    |               nan    |              nan     |            nan     |

## Distribucion de R

| playbook   |   n |   median_r |   std_r |    skew |   min_r |   p05_r |   p95_r |   max_r |
|:-----------|----:|-----------:|--------:|--------:|--------:|--------:|--------:|--------:|
| all        | 254 |     -0.303 |   1.465 |   0.827 |      -1 |      -1 |   2.692 |   5.338 |
| breakout   | 254 |     -0.303 |   1.465 |   0.827 |      -1 |      -1 |   2.692 |   5.338 |
| pullback   |   0 |    nan     | nan     | nan     |     nan |     nan | nan     | nan     |
| hybrid     |   0 |    nan     | nan     | nan     |     nan |     nan | nan     | nan     |

## Equity Curve + Monte Carlo

| playbook   |   final_capital |   total_return_pct |   mc_median_capital |   mc_p05_capital |   mc_p95_capital |   mc_median_drawdown |   mc_max_consec_losses_p95 |
|:-----------|----------------:|-------------------:|--------------------:|-----------------:|-----------------:|---------------------:|---------------------------:|
| all        |         19625.6 |              96.26 |               19477 |          13507.2 |          28805.1 |               -10.13 |                         12 |
| breakout   |         19625.6 |              96.26 |               19477 |          13507.2 |          28805.1 |               -10.13 |                         12 |
| pullback   |           nan   |             nan    |                 nan |            nan   |            nan   |               nan    |                        nan |
| hybrid     |           nan   |             nan    |                 nan |            nan   |            nan   |               nan    |                        nan |

## Veredicto comparativo

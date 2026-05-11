# Comparacion de Playbooks — Fase B

- Capital inicial: **$10,000**
- Riesgo por trade: **1.0%**
- Costos: comision **$1.0** + slippage **0.05%/lado**
- Monte Carlo: **2000** runs (bootstrap)

## Comparacion head-to-head

| playbook   |   n |   win_rate_pct |   expectancy |   expectancy_with_costs |   max_drawdown_pct |   mc_worst_drawdown |   mc_prob_profit_pct |   rolling_sharpe_avg |   edge_degradation |
|:-----------|----:|---------------:|-------------:|------------------------:|-------------------:|--------------------:|---------------------:|---------------------:|-------------------:|
| all        | 254 |          46.85 |        0.305 |                   0.252 |              -9.72 |              -16.39 |                  100 |                 0.19 |             -0.084 |
| breakout   | 254 |          46.85 |        0.305 |                   0.252 |              -9.72 |              -16.39 |                  100 |                 0.19 |             -0.084 |
| pullback   |   0 |         nan    |      nan     |                 nan     |             nan    |              nan    |                  nan |               nan    |            nan     |
| hybrid     |   0 |         nan    |      nan     |                 nan     |             nan    |              nan    |                  nan |               nan    |            nan     |

## Distribucion de R

| playbook   |   n |   median_r |   std_r |    skew |   min_r |   p05_r |   p95_r |   max_r |
|:-----------|----:|-----------:|--------:|--------:|--------:|--------:|--------:|--------:|
| all        | 254 |      -0.21 |   1.484 |   0.807 |      -1 |      -1 |   2.974 |   5.338 |
| breakout   | 254 |      -0.21 |   1.484 |   0.807 |      -1 |      -1 |   2.974 |   5.338 |
| pullback   |   0 |     nan    | nan     | nan     |     nan |     nan | nan     | nan     |
| hybrid     |   0 |     nan    | nan     | nan     |     nan |     nan | nan     | nan     |

## Equity Curve + Monte Carlo

| playbook   |   final_capital |   total_return_pct |   mc_median_capital |   mc_p05_capital |   mc_p95_capital |   mc_median_drawdown |   mc_max_consec_losses_p95 |
|:-----------|----------------:|-------------------:|--------------------:|-----------------:|-----------------:|---------------------:|---------------------------:|
| all        |         21089.9 |              110.9 |             20890.4 |            14483 |          31133.1 |                -9.79 |                         12 |
| breakout   |         21089.9 |              110.9 |             20890.4 |            14483 |          31133.1 |                -9.79 |                         12 |
| pullback   |           nan   |              nan   |               nan   |              nan |            nan   |               nan    |                        nan |
| hybrid     |           nan   |              nan   |               nan   |              nan |            nan   |               nan    |                        nan |

## Veredicto comparativo

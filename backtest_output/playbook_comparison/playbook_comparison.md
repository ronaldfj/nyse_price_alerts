# Comparacion de Playbooks — Fase B

- Capital inicial: **$10,000**
- Riesgo por trade: **1.0%**
- Costos: comision **$1.0** + slippage **0.05%/lado**
- Monte Carlo: **2000** runs (bootstrap)

## Comparacion head-to-head

| playbook   |   n |   win_rate_pct |   expectancy |   expectancy_with_costs |   max_drawdown_pct |   mc_worst_drawdown |   mc_prob_profit_pct |   rolling_sharpe_avg |   edge_degradation |
|:-----------|----:|---------------:|-------------:|------------------------:|-------------------:|--------------------:|---------------------:|---------------------:|-------------------:|
| all        | 307 |          48.53 |        0.314 |                   0.268 |             -13.14 |              -16.16 |                100   |                0.208 |              0.041 |
| breakout   | 283 |          48.06 |        0.326 |                   0.279 |             -14.24 |              -16    |                100   |                0.209 |              0.065 |
| pullback   |  24 |          54.17 |        0.173 |                   0.14  |              -2.62 |               -6.31 |                 81.6 |                0.247 |             -0.106 |
| hybrid     |   0 |         nan    |      nan     |                 nan     |             nan    |              nan    |                nan   |              nan     |            nan     |

## Distribucion de R

| playbook   |   n |   median_r |   std_r |    skew |   min_r |   p05_r |   p95_r |   max_r |
|:-----------|----:|-----------:|--------:|--------:|--------:|--------:|--------:|--------:|
| all        | 307 |     -0.183 |   1.437 |   0.628 |      -1 |      -1 |   2.672 |    4.65 |
| breakout   | 283 |     -0.275 |   1.472 |   0.623 |      -1 |      -1 |   2.761 |    4.65 |
| pullback   |  24 |      0.337 |   0.949 |  -0.111 |      -1 |      -1 |   1.262 |    1.43 |
| hybrid     |   0 |    nan     | nan     | nan     |     nan |     nan | nan     |  nan    |

## Equity Curve + Monte Carlo

| playbook   |   final_capital |   total_return_pct |   mc_median_capital |   mc_p05_capital |   mc_p95_capital |   mc_median_drawdown |   mc_max_consec_losses_p95 |
|:-----------|----------------:|-------------------:|--------------------:|-----------------:|-----------------:|---------------------:|---------------------------:|
| all        |         25354.5 |             153.54 |             25220   |         16617.6  |          38614.4 |                -9.8  |                         11 |
| breakout   |         24348.2 |             143.48 |             24221.2 |         16542.4  |          36394.4 |                -9.65 |                         12 |
| pullback   |         10413.3 |               4.13 |             10433.5 |          9657.14 |          11216   |                -2.97 |                          6 |
| hybrid     |           nan   |             nan    |               nan   |           nan    |            nan   |               nan    |                        nan |

## Veredicto comparativo

- **Mejor expectancy con costos**: `breakout` (0.279R, n=283)
- **Mejor Sharpe rolling**: `pullback` (0.247)
- **Menor drawdown**: `pullback` (-2.62%)

### breakout
- ✅ edge robusto
- Expectancy con costos: **0.279R**
- Sharpe rolling: **0.209**
- Trades: **283**
- Max losses consecutivas (MC p95): **12**

### pullback
- 🟡 edge modesto | ⚠️ edge degradandose
- Expectancy con costos: **0.140R**
- Sharpe rolling: **0.247**
- Trades: **24**
- Max losses consecutivas (MC p95): **6**

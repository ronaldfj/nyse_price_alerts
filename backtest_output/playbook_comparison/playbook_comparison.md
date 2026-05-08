# Comparacion de Playbooks — Fase B

- Capital inicial: **$10,000**
- Riesgo por trade: **1.0%**
- Costos: comision **$1.0** + slippage **0.05%/lado**
- Monte Carlo: **2000** runs (bootstrap)

## Comparacion head-to-head

| playbook   |   n |   win_rate_pct |   expectancy |   expectancy_with_costs |   max_drawdown_pct |   mc_worst_drawdown |   mc_prob_profit_pct |   rolling_sharpe_avg |   edge_degradation |
|:-----------|----:|---------------:|-------------:|------------------------:|-------------------:|--------------------:|---------------------:|---------------------:|-------------------:|
| all        | 270 |          47.04 |        0.3   |                   0.249 |             -11.6  |              -16.25 |                99.95 |                0.189 |             -0.083 |
| breakout   | 249 |          47.39 |        0.322 |                   0.269 |             -12.72 |              -15.71 |               100    |                0.199 |             -0.067 |
| pullback   |  21 |          42.86 |        0.043 |                   0.009 |              -3.84 |               -7.73 |                57.5  |                0.136 |             -0.138 |
| hybrid     |   0 |         nan    |      nan     |                 nan     |             nan    |              nan    |               nan    |              nan     |            nan     |

## Distribucion de R

| playbook   |   n |   median_r |   std_r |    skew |   min_r |   p05_r |   p95_r |   max_r |
|:-----------|----:|-----------:|--------:|--------:|--------:|--------:|--------:|--------:|
| all        | 270 |     -0.19  |   1.459 |   0.812 |      -1 |      -1 |   2.897 |   5.338 |
| breakout   | 249 |     -0.189 |   1.493 |   0.791 |      -1 |      -1 |   2.984 |   5.338 |
| pullback   |  21 |     -0.353 |   0.956 |   0.243 |      -1 |      -1 |   1.28  |   1.43  |
| hybrid     |   0 |    nan     | nan     | nan     |     nan |     nan | nan     | nan     |

## Equity Curve + Monte Carlo

| playbook   |   final_capital |   total_return_pct |   mc_median_capital |   mc_p05_capital |   mc_p95_capital |   mc_median_drawdown |   mc_max_consec_losses_p95 |
|:-----------|----------------:|-------------------:|--------------------:|-----------------:|-----------------:|---------------------:|---------------------------:|
| all        |         21854.6 |             118.55 |             21869.4 |         14967.5  |          32415.4 |                -9.7  |                         11 |
| breakout   |         21679.4 |             116.79 |             22016.2 |         15015.4  |          31948.2 |                -9.35 |                         12 |
| pullback   |         10080.8 |               0.81 |             10080.2 |          9399.81 |          10823.9 |                -3.63 |                          8 |
| hybrid     |           nan   |             nan    |               nan   |           nan    |            nan   |               nan    |                        nan |

## Veredicto comparativo

- **Mejor expectancy con costos**: `breakout` (0.269R, n=249)
- **Mejor Sharpe rolling**: `breakout` (0.199)
- **Menor drawdown**: `pullback` (-3.84%)

### breakout
- ✅ edge robusto
- Expectancy con costos: **0.269R**
- Sharpe rolling: **0.199**
- Trades: **249**
- Max losses consecutivas (MC p95): **12**

### pullback
- ⚠️ marginalmente rentable | ⚠️ edge degradandose
- Expectancy con costos: **0.009R**
- Sharpe rolling: **0.136**
- Trades: **21**
- Max losses consecutivas (MC p95): **8**

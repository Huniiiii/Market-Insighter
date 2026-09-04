# Methodology

## Market moves

- Equities, commodities, and FX use simple close-to-close returns: `P(t) / P(t-1) - 1`.
- Treasury and policy rates use absolute changes multiplied by 100, producing basis points.
- CPI uses 12-observation percent change when represented at monthly frequency.

## Rolling correlation

For two daily-move series, the platform computes the Pearson correlation over a selectable rolling window. A minimum of half the window, and at least five observations, is required.

Correlation is descriptive. It can shift because of policy regimes, volatility, data frequency, common factors, and outliers.

## Event study

Each calendar event is mapped to the first market observation on or after the event date. The engine extracts a trading-day window from `-pre_days` to `+post_days`.

- Price series: cumulative percent move from day -1.
- Yield series: cumulative basis-point move from day -1.
- Aggregation: mean, median, standard deviation, and observation count by relative day.

The bundled event calendar is illustrative. Production work should use time-stamped, licensed consensus and actual-release data, control for overlapping events, and distinguish announcement time from market close.

## Portfolio analytics

The portfolio assumes daily rebalancing, long-only normalized weights, and no transaction costs.

- Annualized return: geometric growth scaled to 252 trading days.
- Volatility: sample daily standard deviation times the square root of 252.
- Sharpe ratio: annualized excess return divided by annualized volatility.
- Beta: covariance with SPY divided by SPY variance.
- Historical VaR: lower empirical return quantile.
- Expected Shortfall: average return at or below the VaR cutoff.
- Maximum drawdown: largest peak-to-trough loss of the wealth index.
- Component risk contribution: Euler decomposition of covariance-model volatility.

## Stress periods

| Scenario | Start | End |
|---|---:|---:|
| Global Financial Crisis | 2008-09-15 | 2009-03-09 |
| COVID selloff | 2020-02-19 | 2020-03-23 |
| 2022 rates shock | 2022-01-03 | 2022-10-14 |

These fixed windows make comparisons reproducible but do not imply that every asset peaked and troughed on the same date.


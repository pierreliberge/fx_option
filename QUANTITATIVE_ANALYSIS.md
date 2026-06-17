# Quantitative Analysis - Monthly USDJPY Long Straddle

## Strategy

The main strategy is a 1-month ATM-forward USDJPY long straddle:

- Buy 1 call and 1 put.
- Strike is set near the 1-month forward at entry.
- Position is rolled monthly.
- Delta is hedged daily using spot USDJPY.
- P&L is expressed in JPY, the domestic currency for USDJPY.

This is a long-volatility strategy. It is long Gamma and long Vega, but it pays Theta every day.

## Economic Rationale

A delta-hedged long straddle can make money when realized spot movement is high enough to compensate for option time decay. The daily hedge monetizes convexity: when spot moves, the option Delta changes, and re-hedging can capture Gamma P&L.

However, the strategy also has two major costs:

- The option premium embeds implied volatility, which can be higher than future realized volatility.
- Theta is negative for a long option position, so the strategy loses value when spot does not move enough.

Therefore, a negative result is economically plausible. It means that, over the tested period, the realized movement and volatility gains were not enough to cover the premium and time decay paid by the systematic long straddle.

## Main Performance Results

For the example run in `run_backtest.py`, using 2024-2025 data:

| Metric | Value |
|---|---:|
| Total P&L | -3,614,046 JPY |
| Sharpe Ratio | -0.57 |
| Sortino Ratio | -1.05 |
| Max Drawdown | -6,252,430 JPY |
| Daily VaR 95% | -253,369 JPY |
| Daily Expected Shortfall 95% | -354,501 JPY |

These results are consistent with a long-volatility strategy that paid more implied volatility than it harvested through realized spot moves.

## Greeks Interpretation

The Greeks attribution in the notebook decomposes daily P&L into:

- Delta: first-order spot exposure before hedging.
- Gamma: convexity benefit from spot moves.
- Vega: sensitivity to changes in implied volatility.
- Theta: daily time decay.

For a long straddle, Gamma should often be positive, while Theta should be negative. The key economic question is whether Gamma and Vega gains exceed Theta losses and initial option premium costs.

## Why Tail Risk Metrics Matter

Sharpe alone is not enough for options because option P&L is nonlinear and can have asymmetric tails. The project therefore also reports:

- Sortino ratio, focused on downside volatility.
- Maximum drawdown, to measure path-dependent capital loss.
- Value-at-Risk, to estimate bad daily losses.
- Expected Shortfall, to measure average losses beyond VaR.

These are better suited to evaluating option strategies than relying only on average return and volatility.

## Signal Extension

The optional `spot_momentum` signal only enters when the absolute spot move over a lookback window exceeds a threshold. It is intentionally simple, but it demonstrates how entries can be conditioned rather than always buying volatility.

In practice, more advanced signals could compare implied volatility against realized volatility, macro event calendars, or trend/regime indicators.

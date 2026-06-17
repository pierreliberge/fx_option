# FX Option Backtesting - User Guide

## Objective

This project builds a compact backtesting engine for USDJPY FX options. Prices are in JPY, the domestic quote currency of USDJPY. The engine supports market-data loading, Garman-Kohlhagen pricing, multi-leg strategies, roll schedules, daily delta hedging, performance metrics, Greeks attribution, and a simple optional entry signal.

## Files

- `fx_backtester/data.py`: loads Parquet files, cleans stacked market data, pivots curves by date/maturity, unpacks volatility surfaces by date/maturity, and interpolates/extrapolates market inputs.
- `fx_backtester/pricing.py`: Garman-Kohlhagen prices and Greeks.
- `fx_backtester/strategy.py`: roll-date generation and multi-leg templates.
- `fx_backtester/backtest.py`: strategy execution, lifecycle management, daily hedging, P&L.
- `fx_backtester/analytics.py`: Sharpe, Sortino, drawdown, VaR, expected shortfall.
- `fx_backtester/plots.py`: chart helpers.
- `run_backtest.py`: one-command example run.
- `notebooks/FX_Option_Backtesting.ipynb`: end-to-end notebook.

## Market Data

The project expects these files in the root folder:

- `usdjpy_spot.parquet`
- `usdjpy_forwardcurve.parquet`
- `usdjpy_depocurve1.parquet`
- `usdjpy_depocurve2.parquet`
- `usdjpy_volatilitysurface.parquet`

For USDJPY, JPY is domestic and USD is foreign. Therefore:

- `usdjpy_depocurve2.parquet` is treated as the JPY domestic curve.
- `usdjpy_depocurve1.parquet` is treated as the USD foreign curve.
- Forward points are divided by 100 before being added to spot, which matches the USDJPY market convention in the provided data.
- Rates and volatilities are converted from annual percentages to decimals.
- Stacked curve data is pivoted into date x maturity tables for faster lookup.
- Stacked volatility data is unpacked into date/maturity slices before the backtest runs.

## Numerical Methods

- Volatility by strike: cubic spline interpolation.
- Volatility strike extrapolation: linear tails.
- Volatility by maturity: linear interpolation/extrapolation.
- Forward and interest-rate curves: linear interpolation/extrapolation by maturity.

## Strategies

Built-in templates:

- `StrategyFactory.straddle(tenor_months=1)`
- `StrategyFactory.ratio_call_spread(tenor_months=1)`
- `StrategyFactory.calendar_call_spread(front_months=1, back_months=3)`

Each strategy is represented as option legs with type, quantity, tenor, strike multiplier, strike, and expiry. The backtester can therefore run multi-leg structures without changing the pricing engine.

## Lifecycle and Hedging

Roll dates can be weekly, monthly, or quarterly. At each roll date, the old position is closed and a new one is opened. The default example uses a 1-month ATM-forward straddle rolled monthly. Delta hedging is performed daily by holding the opposite spot exposure.

## Signal

The default mode is `signal_mode="always"`, which enters at every scheduled roll. A simple optional signal is also available:

```python
BacktestConfig(signal_mode="spot_momentum", momentum_lookback=20, momentum_threshold=0.015)
```

This only enters when the absolute 20-day spot move is above the threshold.

## How To Run

From the project folder:

```powershell
python run_backtest.py
```

Outputs are saved in `outputs/`:

- `straddle_backtest_results.csv`
- `straddle_performance_report.csv`
- `straddle_backtest_charts.png`

## Economic Reading Of The Example

The monthly long straddle is long Gamma and long Vega, but pays Theta. Daily delta hedging tries to monetize realized spot movement: the strategy tends to benefit when USDJPY moves enough for Gamma gains to exceed the option premium decay. It tends to lose when spot is range-bound or when implied volatility falls after entry. The performance report should therefore be read with option-specific risk measures, especially drawdown, VaR, expected shortfall, and the Greeks attribution rather than Sharpe alone.

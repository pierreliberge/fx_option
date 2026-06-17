from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd


def plot_backtest(results: pd.DataFrame):
    fig, axes = plt.subplots(3, 1, figsize=(11, 9), sharex=True)
    results["spot"].plot(ax=axes[0], title="USDJPY spot")
    results["total_pnl"].cumsum().plot(ax=axes[1], title="Cumulative P&L in JPY")
    results[["delta_attr", "gamma_attr", "vega_attr", "theta_attr"]].cumsum().plot(
        ax=axes[2], title="Greeks P&L attribution"
    )
    for ax in axes:
        ax.grid(True, alpha=0.25)
    fig.tight_layout()
    return fig

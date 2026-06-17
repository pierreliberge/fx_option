from __future__ import annotations

import numpy as np
import pandas as pd


def performance_report(results: pd.DataFrame) -> pd.Series:
    pnl = results["total_pnl"].dropna()
    if pnl.empty:
        raise ValueError("No P&L observations available")
    downside = pnl[pnl < 0]
    ann = np.sqrt(252.0)
    sharpe = pnl.mean() / pnl.std(ddof=1) * ann if pnl.std(ddof=1) != 0 else np.nan
    sortino = pnl.mean() / downside.std(ddof=1) * ann if len(downside) > 1 and downside.std(ddof=1) != 0 else np.nan
    equity = pnl.cumsum()
    drawdown = equity - equity.cummax()
    var_95 = pnl.quantile(0.05)
    return pd.Series(
        {
            "total_pnl": pnl.sum(),
            "annualized_pnl": pnl.mean() * 252.0,
            "annualized_vol": pnl.std(ddof=1) * ann,
            "sharpe": sharpe,
            "sortino": sortino,
            "hit_ratio": (pnl > 0).mean(),
            "max_drawdown": drawdown.min(),
            "var_95_daily": var_95,
            "expected_shortfall_95_daily": pnl[pnl <= var_95].mean(),
        }
    )

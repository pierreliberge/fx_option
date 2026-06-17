from __future__ import annotations

from dataclasses import dataclass, replace

import pandas as pd


@dataclass(frozen=True)
class OptionLeg:
    option_type: str
    quantity: float
    strike: float | None = None
    expiry: pd.Timestamp | None = None
    tenor_months: int = 1
    strike_moneyness: float = 1.0

    def with_trade_terms(self, strike: float, expiry: pd.Timestamp) -> "OptionLeg":
        return replace(self, strike=float(strike), expiry=pd.Timestamp(expiry))


class StrategyFactory:
    @staticmethod
    def straddle(tenor_months: int = 1, quantity: float = 1.0) -> list[OptionLeg]:
        return [
            OptionLeg("C", quantity, tenor_months=tenor_months),
            OptionLeg("P", quantity, tenor_months=tenor_months),
        ]

    @staticmethod
    def ratio_call_spread(tenor_months: int = 1) -> list[OptionLeg]:
        return [
            OptionLeg("C", 1.0, tenor_months=tenor_months, strike_moneyness=1.0),
            OptionLeg("C", -2.0, tenor_months=tenor_months, strike_moneyness=1.03),
        ]

    @staticmethod
    def calendar_call_spread(front_months: int = 1, back_months: int = 3) -> list[OptionLeg]:
        return [
            OptionLeg("C", -1.0, tenor_months=front_months, strike_moneyness=1.0),
            OptionLeg("C", 1.0, tenor_months=back_months, strike_moneyness=1.0),
        ]


def generate_roll_dates(
    dates: pd.DatetimeIndex,
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
    frequency: str = "monthly",
) -> pd.DatetimeIndex:
    dates = dates[(dates >= pd.Timestamp(start)) & (dates <= pd.Timestamp(end))]
    if len(dates) == 0:
        return dates
    if frequency == "weekly":
        periods = dates.to_period("W-FRI")
    elif frequency == "quarterly":
        periods = dates.to_period("Q")
    elif frequency == "monthly":
        periods = dates.to_period("M")
    else:
        raise ValueError("frequency must be weekly, monthly or quarterly")
    return dates.to_series().groupby(periods).first().to_numpy()

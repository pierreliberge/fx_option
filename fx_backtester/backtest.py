from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .data import MarketData, year_fraction
from .pricing import garman_kohlhagen
from .strategy import OptionLeg, generate_roll_dates


@dataclass(frozen=True)
class BacktestConfig:
    start: str
    end: str
    roll_frequency: str = "monthly"
    notional: float = 1_000_000.0
    hedge_daily: bool = True
    signal_mode: str = "always"
    momentum_lookback: int = 20
    momentum_threshold: float = 0.015


class OptionBacktester:
    def __init__(self, market: MarketData, config: BacktestConfig):
        self.market = market
        self.config = config

    def _new_position(self, date: pd.Timestamp, templates: list[OptionLeg]) -> list[OptionLeg]:
        spot = self.market.spot_on(date)
        legs = []
        for leg in templates:
            expiry = date + pd.DateOffset(months=leg.tenor_months)
            forward = self.market.forward_outright(date, expiry)
            strike = forward * leg.strike_moneyness if leg.strike is None else leg.strike
            legs.append(leg.with_trade_terms(strike=strike, expiry=expiry))
        return legs

    def _entry_signal(self, dates: pd.DatetimeIndex, idx: int) -> bool:
        if self.config.signal_mode == "always":
            return True
        if self.config.signal_mode != "spot_momentum":
            raise ValueError("signal_mode must be 'always' or 'spot_momentum'")
        lookback = self.config.momentum_lookback
        if idx < lookback:
            return False
        spot_now = self.market.spot_on(dates[idx])
        spot_then = self.market.spot_on(dates[idx - lookback])
        return abs(spot_now / spot_then - 1.0) >= self.config.momentum_threshold

    def _value_position(self, date: pd.Timestamp, legs: list[OptionLeg]) -> dict[str, float]:
        spot = self.market.spot_on(date)
        value = delta = gamma = vega = theta = 0.0
        weighted_vol = vol_weight = 0.0
        for leg in legs:
            assert leg.strike is not None and leg.expiry is not None
            if date >= leg.expiry:
                tau = 0.0
                rd = rf = vol = 0.0
            else:
                tau = year_fraction(date, leg.expiry)
                rd = self.market.domestic_rate(date, leg.expiry)
                rf = self.market.foreign_rate(date, leg.expiry)
                vol = self.market.volatility(date, leg.expiry, leg.strike)
            px = garman_kohlhagen(spot, leg.strike, tau, rd, rf, vol, leg.option_type)
            multiplier = leg.quantity * self.config.notional
            value += multiplier * px.price
            delta += multiplier * px.delta
            gamma += multiplier * px.gamma
            vega += multiplier * px.vega
            theta += multiplier * px.theta
            weighted_vol += abs(multiplier * px.vega) * vol
            vol_weight += abs(multiplier * px.vega)
        implied_vol = weighted_vol / vol_weight if vol_weight > 0 else 0.0
        return {
            "option_value": value,
            "delta": delta,
            "gamma": gamma,
            "vega": vega,
            "theta": theta,
            "implied_vol": implied_vol,
        }

    def run(self, templates: list[OptionLeg]) -> pd.DataFrame:
        dates = self.market.business_dates(self.config.start, self.config.end)
        roll_dates = set(pd.to_datetime(generate_roll_dates(dates, self.config.start, self.config.end, self.config.roll_frequency)))
        if len(dates) < 2:
            raise ValueError("Backtest period is too short")

        active_legs: list[OptionLeg] = []
        cash = 0.0
        hedge_units = 0.0
        previous = None
        rows = []

        for idx, date in enumerate(dates):
            if not active_legs or date in roll_dates or any(leg.expiry is not None and date >= leg.expiry for leg in active_legs):
                if active_legs:
                    old = self._value_position(date, active_legs)
                    cash += old["option_value"]
                    active_legs = []
                if self._entry_signal(dates, idx):
                    active_legs = self._new_position(date, templates)
                    new_value = self._value_position(date, active_legs)
                    cash -= new_value["option_value"]

            value = self._value_position(date, active_legs) if active_legs else {
                "option_value": 0.0,
                "delta": 0.0,
                "gamma": 0.0,
                "vega": 0.0,
                "theta": 0.0,
                "implied_vol": 0.0,
            }
            spot = self.market.spot_on(date)
            hedge_value = hedge_units * spot
            nav = cash + value["option_value"] + hedge_value

            if previous is None:
                total_pnl = option_pnl = hedge_pnl = 0.0
                delta_attr = gamma_attr = vega_attr = theta_attr = 0.0
            else:
                dspot = spot - previous["spot"]
                option_pnl = value["option_value"] - previous["option_value"]
                hedge_pnl = previous["hedge_units"] * dspot
                total_pnl = nav - previous["nav"]
                delta_attr = previous["delta"] * dspot
                gamma_attr = 0.5 * previous["gamma"] * dspot * dspot
                vega_attr = previous["vega"] * (value["implied_vol"] - previous["implied_vol"])
                theta_attr = previous["theta"]

            if self.config.hedge_daily:
                target_hedge = -value["delta"]
                cash -= (target_hedge - hedge_units) * spot
                hedge_units = target_hedge
                hedge_value = hedge_units * spot
                nav = cash + value["option_value"] + hedge_value

            row = {
                "date": date,
                "spot": spot,
                "option_value": value["option_value"],
                "delta": value["delta"],
                "gamma": value["gamma"],
                "vega": value["vega"],
                "theta": value["theta"],
                "implied_vol": value["implied_vol"],
                "hedge_units": hedge_units,
                "hedge_value": hedge_value,
                "cash": cash,
                "nav": nav,
                "total_pnl": total_pnl,
                "option_pnl": option_pnl,
                "hedge_pnl": hedge_pnl,
                "delta_attr": delta_attr,
                "gamma_attr": gamma_attr,
                "vega_attr": vega_attr,
                "theta_attr": theta_attr,
            }
            rows.append(row)
            previous = row

        return pd.DataFrame(rows).set_index("date")

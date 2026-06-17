from __future__ import annotations

from dataclasses import dataclass
from math import exp, log, sqrt

from scipy.stats import norm


@dataclass(frozen=True)
class OptionPrice:
    price: float
    delta: float
    gamma: float
    vega: float
    theta: float


def garman_kohlhagen(
    spot: float,
    strike: float,
    tau: float,
    rd: float,
    rf: float,
    vol: float,
    option_type: str,
) -> OptionPrice:
    """Price an FX option in domestic currency under Garman-Kohlhagen."""
    option_type = option_type.upper()
    if tau <= 0:
        intrinsic = max(spot - strike, 0.0) if option_type == "C" else max(strike - spot, 0.0)
        delta = 1.0 if option_type == "C" and spot > strike else -1.0 if option_type == "P" and spot < strike else 0.0
        return OptionPrice(intrinsic, delta, 0.0, 0.0, 0.0)

    vol = max(float(vol), 1e-8)
    sqrt_t = sqrt(tau)
    d1 = (log(spot / strike) + (rd - rf + 0.5 * vol * vol) * tau) / (vol * sqrt_t)
    d2 = d1 - vol * sqrt_t
    df_d = exp(-rd * tau)
    df_f = exp(-rf * tau)

    if option_type == "C":
        price = spot * df_f * norm.cdf(d1) - strike * df_d * norm.cdf(d2)
        delta = df_f * norm.cdf(d1)
        theta = (
            -spot * df_f * norm.pdf(d1) * vol / (2.0 * sqrt_t)
            + rf * spot * df_f * norm.cdf(d1)
            - rd * strike * df_d * norm.cdf(d2)
        )
    elif option_type == "P":
        price = strike * df_d * norm.cdf(-d2) - spot * df_f * norm.cdf(-d1)
        delta = -df_f * norm.cdf(-d1)
        theta = (
            -spot * df_f * norm.pdf(d1) * vol / (2.0 * sqrt_t)
            - rf * spot * df_f * norm.cdf(-d1)
            + rd * strike * df_d * norm.cdf(-d2)
        )
    else:
        raise ValueError("option_type must be 'C' or 'P'")

    gamma = df_f * norm.pdf(d1) / (spot * vol * sqrt_t)
    vega = spot * df_f * norm.pdf(d1) * sqrt_t
    return OptionPrice(float(price), float(delta), float(gamma), float(vega), float(theta / 365.0))

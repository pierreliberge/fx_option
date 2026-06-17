from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.interpolate import CubicSpline


def year_fraction(start: pd.Timestamp, end: pd.Timestamp) -> float:
    return max((pd.Timestamp(end) - pd.Timestamp(start)).days / 365.0, 0.0)


def _clean_market_frame(df: pd.DataFrame, maturity_col: str = "Maturity") -> pd.DataFrame:
    df = df.copy()
    df["DATE"] = pd.to_datetime(df["DATE"])
    df["MID_PRICE"] = pd.to_numeric(df["MID_PRICE"], errors="coerce")
    if maturity_col in df.columns:
        df[maturity_col] = pd.to_datetime(df[maturity_col])
    return df.dropna(subset=["DATE", "MID_PRICE"])


def _linear_interp_extrap(x: np.ndarray, y: np.ndarray, x0: float) -> float:
    order = np.argsort(x)
    x = np.asarray(x, dtype=float)[order]
    y = np.asarray(y, dtype=float)[order]
    keep = np.isfinite(x) & np.isfinite(y)
    x, y = x[keep], y[keep]
    uniq, idx = np.unique(x, return_index=True)
    x, y = uniq, y[idx]
    if len(x) == 0:
        raise ValueError("No valid market points available for interpolation")
    if len(x) == 1:
        return float(y[0])
    if x0 <= x[0]:
        slope = (y[1] - y[0]) / (x[1] - x[0])
        return float(y[0] + slope * (x0 - x[0]))
    if x0 >= x[-1]:
        slope = (y[-1] - y[-2]) / (x[-1] - x[-2])
        return float(y[-1] + slope * (x0 - x[-1]))
    return float(np.interp(x0, x, y))


def _cubic_strike_linear_tail(strikes: np.ndarray, vols: np.ndarray, strike: float) -> float:
    order = np.argsort(strikes)
    x = np.asarray(strikes, dtype=float)[order]
    y = np.asarray(vols, dtype=float)[order]
    keep = np.isfinite(x) & np.isfinite(y)
    x, y = x[keep], y[keep]
    uniq, idx = np.unique(x, return_index=True)
    x, y = uniq, y[idx]
    if len(x) < 4:
        return _linear_interp_extrap(x, y, strike)
    if strike < x[0]:
        return _linear_interp_extrap(x[:2], y[:2], strike)
    if strike > x[-1]:
        return _linear_interp_extrap(x[-2:], y[-2:], strike)
    return float(CubicSpline(x, y, bc_type="natural")(strike))


@dataclass
class MarketData:
    spot: pd.DataFrame
    forwards: pd.DataFrame
    domestic_rates: pd.DataFrame
    foreign_rates: pd.DataFrame
    vols: pd.DataFrame
    forward_table: pd.DataFrame
    domestic_rate_table: pd.DataFrame
    foreign_rate_table: pd.DataFrame
    vol_surfaces: dict[pd.Timestamp, dict[pd.Timestamp, pd.DataFrame]]
    forward_point_scale: float = 100.0

    @classmethod
    def from_folder(cls, folder: str | Path) -> "MarketData":
        folder = Path(folder)
        spot = _clean_market_frame(pd.read_parquet(folder / "usdjpy_spot.parquet"))
        forwards = _clean_market_frame(pd.read_parquet(folder / "usdjpy_forwardcurve.parquet"))
        usd_rates = _clean_market_frame(pd.read_parquet(folder / "usdjpy_depocurve1.parquet"))
        jpy_rates = _clean_market_frame(pd.read_parquet(folder / "usdjpy_depocurve2.parquet"))
        vols = pd.read_parquet(folder / "usdjpy_volatilitysurface.parquet").copy()
        vols["DATE"] = pd.to_datetime(vols["DATE"])
        vols["MATURITY"] = pd.to_datetime(vols["MATURITY"])
        vols["MID_PRICE"] = pd.to_numeric(vols["MID_PRICE"], errors="coerce") / 100.0
        vols["MID_STRIKE"] = pd.to_numeric(vols["MID_STRIKE"], errors="coerce")
        vols = vols.dropna(subset=["DATE", "MATURITY", "MID_PRICE", "MID_STRIKE"])
        vols = vols.sort_values(["DATE", "MATURITY", "MID_STRIKE"]).set_index("DATE", drop=False)

        spot = spot.sort_values("DATE").set_index("DATE")
        forward_table = _pivot_curve(forwards)
        domestic_rate_table = _pivot_curve(jpy_rates)
        foreign_rate_table = _pivot_curve(usd_rates)
        return cls(
            spot=spot,
            forwards=forwards,
            domestic_rates=jpy_rates,
            foreign_rates=usd_rates,
            vols=vols,
            forward_table=forward_table,
            domestic_rate_table=domestic_rate_table,
            foreign_rate_table=foreign_rate_table,
            vol_surfaces={},
        )

    @property
    def dates(self) -> pd.DatetimeIndex:
        return pd.DatetimeIndex(self.spot.index.unique()).sort_values()

    def spot_on(self, date: pd.Timestamp) -> float:
        return float(self.spot.loc[pd.Timestamp(date), "MID_PRICE"])

    def curve_rate(self, curve: pd.DataFrame, date: pd.Timestamp, maturity: pd.Timestamp) -> float:
        date = pd.Timestamp(date)
        maturity = pd.Timestamp(maturity)
        table = self._table_for_curve(curve)
        if date not in table.index:
            raise KeyError(f"No curve data for {date.date()}")
        row = table.loc[date].dropna()
        tau = pd.Index(row.index).map(lambda m: year_fraction(date, m)).to_numpy()
        rate = row.to_numpy(dtype=float) / 100.0
        return _linear_interp_extrap(tau, rate, year_fraction(date, maturity))

    def _table_for_curve(self, curve: pd.DataFrame) -> pd.DataFrame:
        if curve is self.domestic_rates:
            return self.domestic_rate_table
        if curve is self.foreign_rates:
            return self.foreign_rate_table
        if curve is self.forwards:
            return self.forward_table
        return _pivot_curve(curve)

    def domestic_rate(self, date: pd.Timestamp, maturity: pd.Timestamp) -> float:
        return self.curve_rate(self.domestic_rates, date, maturity)

    def foreign_rate(self, date: pd.Timestamp, maturity: pd.Timestamp) -> float:
        return self.curve_rate(self.foreign_rates, date, maturity)

    def forward_outright(self, date: pd.Timestamp, maturity: pd.Timestamp) -> float:
        date = pd.Timestamp(date)
        spot = self.spot_on(date)
        if date not in self.forward_table.index:
            raise KeyError(f"No forward curve data for {date.date()}")
        row = self.forward_table.loc[date].dropna()
        tau = pd.Index(row.index).map(lambda m: year_fraction(date, m)).to_numpy()
        points = row.to_numpy(dtype=float)
        fwd_points = _linear_interp_extrap(tau, points, year_fraction(date, maturity))
        return spot + fwd_points / self.forward_point_scale

    def volatility(self, date: pd.Timestamp, maturity: pd.Timestamp, strike: float) -> float:
        date = pd.Timestamp(date)
        maturity = pd.Timestamp(maturity)
        surfaces = self.vol_surfaces.get(date)
        if not surfaces:
            try:
                date_vols = self.vols.loc[[date]].reset_index(drop=True)
            except KeyError as exc:
                raise KeyError(f"No volatility surface for {date.date()}") from exc
            self.vol_surfaces[date] = _unpack_vol_surfaces(date_vols)[date]
            surfaces = self.vol_surfaces[date]

        rows = []
        for mat, g in surfaces.items():
            rows.append(
                (
                    year_fraction(date, mat),
                    _cubic_strike_linear_tail(
                        g["MID_STRIKE"].to_numpy(),
                        g["MID_PRICE"].to_numpy(),
                        strike,
                    ),
                )
            )
        tau_grid = np.array([r[0] for r in rows], dtype=float)
        vol_grid = np.array([r[1] for r in rows], dtype=float)
        vol = _linear_interp_extrap(tau_grid, vol_grid, year_fraction(date, maturity))
        return max(float(vol), 1e-4)

    def business_dates(self, start: str | pd.Timestamp, end: str | pd.Timestamp) -> pd.DatetimeIndex:
        dates = self.dates
        mask = (dates >= pd.Timestamp(start)) & (dates <= pd.Timestamp(end))
        return dates[mask]


def _pivot_curve(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.pivot_table(index="DATE", columns="Maturity", values="MID_PRICE", aggfunc="last")
        .sort_index()
        .sort_index(axis=1)
    )


def _unpack_vol_surfaces(vols: pd.DataFrame) -> dict[pd.Timestamp, dict[pd.Timestamp, pd.DataFrame]]:
    surfaces: dict[pd.Timestamp, dict[pd.Timestamp, pd.DataFrame]] = {}
    for (date, maturity), group in vols.groupby(["DATE", "MATURITY"], sort=True):
        surface_slice = (
            group[["MID_STRIKE", "MID_PRICE"]]
            .groupby("MID_STRIKE", as_index=False)
            .mean()
            .sort_values("MID_STRIKE")
        )
        surfaces.setdefault(pd.Timestamp(date), {})[pd.Timestamp(maturity)] = surface_slice
    return surfaces

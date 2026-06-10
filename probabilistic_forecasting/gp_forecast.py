"""Gaussian Process regression with 90% bands and outlier flagging.

Kernel: ConstantKernel * RBF + WhiteNoise — RBF captures the smooth trend,
WhiteNoise absorbs measurement noise, ConstantKernel sets the prior variance.
All bounds are wide enough for sklearn to fit by ML II without us tuning.

Outlier handling (deliberately conservative — earlier versions falsely flagged
real monotonic trends): only runs when n >= 8. A point is flagged when its
residual exceeds BOTH 3 x MAD-sigma AND 10% of the y-range, and never more
than 25% of points are stripped. Flagged years are reported in the output
JSON so the dashboard can show why a value was set aside.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, ConstantKernel, WhiteKernel


@dataclass
class GPForecast:
    years: list[int]            # union of input years + projection years
    mean: list[float]
    upper_90: list[float]
    lower_90: list[float]
    outliers_flagged: list[int]
    kernel_repr: str

    def to_dict(self) -> dict:
        return {
            "years": self.years,
            "mean": self.mean,
            "upper_90": self.upper_90,
            "lower_90": self.lower_90,
            "outliers_flagged": self.outliers_flagged,
            "model": "gaussian_process",
            "kernel": self.kernel_repr,
        }


def _build_kernel(y_scale: float) -> object:
    y_scale = max(y_scale, 1e-3)
    return (
        ConstantKernel(y_scale, (1e-3, 1e6))
        * RBF(length_scale=5.0, length_scale_bounds=(1.0, 500.0))
        + WhiteKernel(noise_level=max(y_scale * 0.05, 1e-4),
                      noise_level_bounds=(1e-8, max(y_scale * 4, 1e-2)))
    )


def fit_gp(
    years: list[int],
    values: list[float],
    horizon_years: int,
    outlier_z: float = 3.0,
) -> GPForecast:
    """Fit a GP and project `horizon_years` past the last observation."""
    if len(years) < 4:
        raise ValueError(f"need at least 4 observations, got {len(years)}")

    x = np.array(years, dtype=float)
    y = np.array(values, dtype=float)

    # Normalize x around its mean to keep the RBF length scale interpretable
    # in units of years.
    x_mean = x.mean()
    x_n = (x - x_mean).reshape(-1, 1)
    y_scale = float(np.var(y)) or 1.0

    kernel = _build_kernel(y_scale)
    gp = GaussianProcessRegressor(
        kernel=kernel,
        n_restarts_optimizer=5,
        alpha=1e-6,  # tiny — WhiteKernel handles the real noise
        normalize_y=False,
        random_state=0,
    ).fit(x_n, y)

    # Residual-based outlier flagging on the training set.
    # Skip entirely when n is small — with few points, MAD becomes unstable
    # and the most recent observations of a monotonic series get falsely
    # flagged as outliers (we saw this on SLR with the dashboard's seed data).
    outliers_flagged: list[int] = []
    if len(years) >= 8:
        y_hat, _ = gp.predict(x_n, return_std=True)
        residuals = y - y_hat
        mad = float(np.median(np.abs(residuals - np.median(residuals))))
        # Floor sigma against the overall y std so a tight fit can't shrink
        # the threshold until normal data looks anomalous.
        sigma_mad = mad * 1.4826
        sigma_y = float(np.std(y)) * 0.15
        sigma = max(sigma_mad, sigma_y, 1e-6)
        # Require BOTH: residual exceeds z*sigma AND exceeds 10% of y range.
        # The second guard kills false positives on clean monotonic data.
        y_range = float(np.ptp(y))
        abs_floor = max(0.1 * y_range, 1e-6)
        outlier_mask = (np.abs(residuals) > outlier_z * sigma) & (np.abs(residuals) > abs_floor)
        # Never strip more than 25% of points.
        if outlier_mask.sum() > len(y) // 4:
            outlier_mask[:] = False
        outliers_flagged = [int(yr) for yr, m in zip(years, outlier_mask) if m]

        if outliers_flagged:
            keep = ~outlier_mask
            x_keep = x_n[keep]
            y_keep = y[keep]
            gp = GaussianProcessRegressor(
                kernel=_build_kernel(float(np.var(y_keep))),
                n_restarts_optimizer=5,
                alpha=1e-6,
                normalize_y=False,
                random_state=0,
            ).fit(x_keep, y_keep)

    # Project: union of original years and future horizon
    last_year = int(x.max())
    proj_years = list(range(last_year + 1, last_year + horizon_years + 1))
    all_years = list(years) + proj_years
    x_all = (np.array(all_years, dtype=float) - x_mean).reshape(-1, 1)
    mean, std = gp.predict(x_all, return_std=True)

    # 90% band ≈ 1.645σ for a Gaussian
    z = 1.645
    upper = mean + z * std
    lower = mean - z * std

    return GPForecast(
        years=all_years,
        mean=[round(float(v), 3) for v in mean],
        upper_90=[round(float(v), 3) for v in upper],
        lower_90=[round(float(v), 3) for v in lower],
        outliers_flagged=outliers_flagged,
        kernel_repr=str(gp.kernel_),
    )

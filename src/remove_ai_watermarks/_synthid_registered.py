"""Opt-in scale registration for the measured periodic SynthID carrier."""

# The optional numeric libraries do not provide complete types for this path.
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import cv2
import numpy as np

from remove_ai_watermarks.synthid_detector import folded_template_score

if TYPE_CHECKING:
    from numpy.typing import NDArray

_PYRAMID_SCALES = (0.75, 1.0, 1.25)
_SEARCH_PERIODS = np.linspace(5.0, 32.0, 541, dtype=np.float64)
_CANONICAL_PERIODS = np.linspace(7.5, 24.5, 1701, dtype=np.float64)
_PERIOD_THRESHOLDS = (
    (7.5, 8.5, 0.3770629524888979),
    (8.5, 10.0, 0.25174716660523494),
    (10.0, 12.0, 0.284692023502354),
    (12.0, 14.0, 0.19794247706938645),
    (14.0, 16.0, 0.33930082812296375),
    (16.0, 18.0, 0.28915284982686323),
    (18.0, 20.0, 0.22885510746595789),
    (20.0, 22.0, 0.24570317032768269),
    (22.0, 24.5, 0.3142958338390489),
)
REGISTERED_HIGH_BAND_THRESHOLD = 0.075


@dataclass(frozen=True)
class RegisteredComponents:
    """Calibrated components of one scale-registered decision."""

    raw_score: float
    amplitude_threshold: float
    selected_period: float
    spectral_period: float
    high_band_score: float

    @property
    def decision_score(self) -> float:
        """Return a statistic that reaches one only when every gate passes."""
        if self.selected_period != self.spectral_period:
            return 0.0
        return min(
            self.raw_score / self.amplitude_threshold,
            self.high_band_score / REGISTERED_HIGH_BAND_THRESHOLD,
        )


def _resize(pixels: NDArray[Any], width: int, height: int) -> NDArray[Any]:
    interpolation = cv2.INTER_AREA if width < pixels.shape[1] else cv2.INTER_CUBIC
    return np.asarray(cv2.resize(pixels, (width, height), interpolation=interpolation))


def _template_frequency_features(
    template: NDArray[Any],
) -> tuple[NDArray[Any], NDArray[Any], NDArray[Any]]:
    spectrum = np.fft.fft2(template, axes=(0, 1))
    power = np.sum(np.abs(spectrum) ** 2, axis=2)
    power[0, 0] = 0.0
    indices = np.argsort(power.ravel())[::-1][:30]
    rows, columns = np.unravel_index(indices, power.shape)
    height, width = template.shape[:2]
    signed_rows = np.where(rows <= height // 2, rows, rows - height)
    signed_columns = np.where(columns <= width // 2, columns, columns - width)
    harmonics = np.column_stack((signed_rows, signed_columns)).astype(np.float64)
    return harmonics, spectrum[rows, columns], spectrum


def _bilinear_sample(
    spectrum: NDArray[Any],
    y: NDArray[Any],
    x: NDArray[Any],
) -> NDArray[Any]:
    height, width = spectrum.shape
    y_floor = np.floor(y)
    x_floor = np.floor(x)
    y0 = y_floor.astype(np.int64) % height
    x0 = x_floor.astype(np.int64) % width
    y1 = (y0 + 1) % height
    x1 = (x0 + 1) % width
    dy = y - y_floor
    dx = x - x_floor
    return (
        spectrum[y0, x0] * (1.0 - dy) * (1.0 - dx)
        + spectrum[y1, x0] * dy * (1.0 - dx)
        + spectrum[y0, x1] * (1.0 - dy) * dx
        + spectrum[y1, x1] * dy * dx
    )


def _spectral_curve(
    pixels: NDArray[Any],
    periods: NDArray[Any],
    harmonics: NDArray[Any],
    coefficients: NDArray[Any],
) -> NDArray[Any]:
    height, width = pixels.shape[:2]
    y = (periods[:, None] ** -1) * harmonics[None, :, 0] * height
    x = (periods[:, None] ** -1) * harmonics[None, :, 1] * width
    sampled = np.empty((len(periods), len(harmonics), 3), dtype=np.complex128)
    for channel in range(3):
        residual = pixels[:, :, channel].astype(np.float32)
        residual -= cv2.GaussianBlur(
            residual,
            (0, 0),
            sigmaX=1.0,
            sigmaY=1.0,
            borderType=cv2.BORDER_REFLECT_101,
        )
        spectrum = np.fft.fft2(residual)
        sampled[:, :, channel] = _bilinear_sample(spectrum, y % height, x % width)
    numerator = np.real(np.sum(np.conj(coefficients)[None, :, :] * sampled, axis=(1, 2)))
    denominator = np.linalg.norm(coefficients) * np.linalg.norm(sampled, axis=(1, 2))
    return np.divide(
        numerator,
        denominator,
        out=np.zeros_like(numerator),
        where=denominator > 0.0,
    )


def _period_candidates(
    periods: NDArray[Any],
    scores: NDArray[Any],
    count: int = 3,
) -> list[float]:
    candidates: list[float] = []
    for index in np.argsort(scores)[::-1]:
        period = float(periods[index])
        if any(abs(period - existing_period) < 0.25 for existing_period in candidates):
            continue
        candidates.append(period)
        if len(candidates) == count:
            break
    return candidates


def _period_threshold(period: float) -> float:
    for index, (lower, upper, threshold) in enumerate(_PERIOD_THRESHOLDS):
        if lower <= period < upper or (index == len(_PERIOD_THRESHOLDS) - 1 and period == upper):
            return threshold
    raise ValueError(f"registered period {period} is outside the calibrated range")


def _high_band_score(
    folded: NDArray[Any],
    template_spectrum: NDArray[Any],
) -> float:
    folded_spectrum = np.fft.fft2(folded, axes=(0, 1))
    tile_height, tile_width = template_spectrum.shape[:2]
    y_coordinates = np.minimum(np.arange(tile_height), tile_height - np.arange(tile_height))
    x_coordinates = np.minimum(np.arange(tile_width), tile_width - np.arange(tile_width))
    radius = np.sqrt(y_coordinates[:, None] ** 2 + x_coordinates[None, :] ** 2)
    correlations = []
    for lower, upper in ((4.5, 6.5), (6.5, 12.0)):
        mask = (radius >= lower) & (radius < upper)
        selected_folded = folded_spectrum[mask]
        selected_template = template_spectrum[mask]
        denominator = np.linalg.norm(selected_folded) * np.linalg.norm(selected_template)
        correlations.append(
            float(np.real(np.vdot(selected_template, selected_folded)) / denominator) if denominator > 0.0 else 0.0
        )
    return min(correlations)


def _best_canonical(
    pixels: NDArray[Any],
    periods: list[float],
    template: NDArray[Any],
    sigma: float,
) -> tuple[float, NDArray[Any], NDArray[Any], float]:
    best_score = -math.inf
    best_canonical: NDArray[Any] | None = None
    best_folded: NDArray[Any] | None = None
    best_period: float | None = None
    for period in periods:
        predicted_width = round(pixels.shape[1] * template.shape[1] / period)
        for delta in range(-4, 5):
            width = predicted_width + delta
            height = round(pixels.shape[0] * width / pixels.shape[1])
            canonical = _resize(pixels, width, height)
            score, folded = folded_template_score(canonical, template, sigma)
            if score > best_score:
                best_score = score
                best_canonical = canonical
                best_folded = folded
                best_period = period
    if best_canonical is None or best_folded is None or best_period is None:
        raise RuntimeError("scale registration produced no canonical view")
    return float(best_score), best_canonical, best_folded, best_period


def _quadrant_median(
    canonical: NDArray[Any],
    template: NDArray[Any],
    sigma: float,
) -> float:
    tile_height, tile_width = template.shape[:2]
    split_y = max(tile_height, (canonical.shape[0] // (2 * tile_height)) * tile_height)
    split_x = max(tile_width, (canonical.shape[1] // (2 * tile_width)) * tile_width)
    scores = []
    for region in (
        canonical[:split_y, :split_x],
        canonical[:split_y, split_x:],
        canonical[split_y:, :split_x],
        canonical[split_y:, split_x:],
    ):
        score, _folded = folded_template_score(region, template, sigma)
        scores.append(score)
    return float(np.median(scores))


def _pyramid_locked_mean(
    pixels: NDArray[Any],
    harmonics: NDArray[Any],
    coefficients: NDArray[Any],
    base_curve: NDArray[Any],
) -> float:
    curves = []
    candidates = []
    for scale in _PYRAMID_SCALES:
        if scale == 1.0:
            curve = base_curve
        else:
            level = _resize(
                pixels,
                max(16, round(pixels.shape[1] * scale)),
                max(16, round(pixels.shape[0] * scale)),
            )
            curve = _spectral_curve(level, _SEARCH_PERIODS, harmonics, coefficients)
        curves.append(curve)
        candidates.append(_period_candidates(_SEARCH_PERIODS, curve))
    combinations = itertools.product(*candidates)

    def spread(combination: tuple[float, ...]) -> float:
        normalized_periods = [
            candidate / scale
            for candidate, scale in zip(
                combination,
                _PYRAMID_SCALES,
                strict=True,
            )
        ]
        return float(np.std(np.log(normalized_periods)))

    best = min(
        combinations,
        key=spread,
    )
    base_period = float(np.median([candidate / scale for candidate, scale in zip(best, _PYRAMID_SCALES, strict=True)]))
    locked = [
        float(np.interp(base_period * scale, _SEARCH_PERIODS, curve))
        for curve, scale in zip(curves, _PYRAMID_SCALES, strict=True)
    ]
    return float(np.mean(locked))


def registered_components(
    pixels: NDArray[Any],
    template: NDArray[Any],
    sigma: float,
) -> RegisteredComponents:
    """Measure a carrier after bounded scale registration."""
    harmonics, coefficients, template_spectrum = _template_frequency_features(template)
    combined_periods = np.concatenate((_SEARCH_PERIODS, _CANONICAL_PERIODS))
    combined_curve = _spectral_curve(pixels, combined_periods, harmonics, coefficients)
    base_curve = combined_curve[: len(_SEARCH_PERIODS)]
    canonical_curve = combined_curve[len(_SEARCH_PERIODS) :]
    candidates = _period_candidates(_CANONICAL_PERIODS, canonical_curve)
    baseline, canonical, folded, selected_period = _best_canonical(pixels, candidates, template, sigma)
    quadrant = _quadrant_median(canonical, template, sigma)
    pyramid = _pyramid_locked_mean(
        pixels,
        harmonics,
        coefficients,
        base_curve,
    )
    raw_score = float((baseline + quadrant + pyramid) / 3.0)
    return RegisteredComponents(
        raw_score=raw_score,
        amplitude_threshold=_period_threshold(selected_period),
        selected_period=selected_period,
        spectral_period=candidates[0],
        high_band_score=_high_band_score(folded, template_spectrum),
    )


def registered_score(
    pixels: NDArray[Any],
    template: NDArray[Any],
    sigma: float,
) -> float:
    """Return the calibrated registered decision statistic."""
    return registered_components(pixels, template, sigma).decision_score

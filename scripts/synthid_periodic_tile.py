"""Shared periodic-residual helpers for SynthID research probes."""

from __future__ import annotations

import cv2
import numpy as np


def fold_residual_template(
    pixels: np.ndarray,
    *,
    tile_height: int,
    tile_width: int,
    denoise_sigma: float,
) -> np.ndarray:
    """Estimate a zero-mean periodic residual template by modulo folding."""
    if pixels.ndim != 3 or pixels.shape[2] != 3:
        raise ValueError("pixels must have shape (height, width, 3)")
    if tile_height < 1 or tile_width < 1 or denoise_sigma <= 0.0:
        raise ValueError("tile dimensions and denoise sigma must be positive")
    height, width = pixels.shape[:2]
    if height % tile_height != 0 or width % tile_width != 0:
        raise ValueError("image geometry must be divisible by the tile geometry")
    source = pixels.astype(np.float32)
    denoised = cv2.GaussianBlur(
        source,
        (0, 0),
        sigmaX=denoise_sigma,
        sigmaY=denoise_sigma,
        borderType=cv2.BORDER_REFLECT_101,
    )
    residual = source - denoised
    repeats_y = height // tile_height
    repeats_x = width // tile_width
    folded = residual.reshape(repeats_y, tile_height, repeats_x, tile_width, 3).mean(
        axis=(0, 2),
        dtype=np.float64,
    )
    return folded - np.mean(folded, axis=(0, 1), keepdims=True)


def unit_tile(tile: np.ndarray) -> tuple[np.ndarray, float]:
    """Return TILE normalized by its L2 norm and the original norm."""
    norm = float(np.linalg.norm(tile))
    if norm == 0.0:
        return np.zeros_like(tile, dtype=np.float64), 0.0
    return np.asarray(tile, dtype=np.float64) / norm, norm


def cyclic_tile_correlations(template: np.ndarray, tile: np.ndarray) -> np.ndarray:
    """Return correlations for every cyclic spatial shift of TILE."""
    if template.shape != tile.shape or template.ndim != 3:
        raise ValueError("template and tile must have identical three-dimensional shapes")
    template_spectrum = np.fft.fft2(template, axes=(0, 1))
    tile_spectrum = np.fft.fft2(tile, axes=(0, 1))
    return np.fft.ifft2(np.sum(template_spectrum * np.conj(tile_spectrum), axis=2)).real

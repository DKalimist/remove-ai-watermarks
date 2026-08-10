"""Discover and score a shared spectral carrier from exact image pairs.

This is a research harness, not a production SynthID detector. Pair provenance
and oracle labels remain external evidence. The harness deliberately separates
template discovery from single-image scoring and stores arrays in NPZ without
pickle.

Usage:
    uv run python scripts/synthid_spectral_probe.py discover \
        --pair clean.png marked.png --pair clean2.png marked2.png \
        --template-out .local-eval/synthid/template.npz \
        --report-out .local-eval/synthid/pair-report.json

    uv run python scripts/synthid_spectral_probe.py score \
        .local-eval/synthid/template.npz image.png other.png
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from itertools import combinations
from pathlib import Path

import click
import numpy as np
from PIL import Image, ImageFilter

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class PairMeasurement:
    """Pixel-domain measurements for one exact clean/marked pair."""

    clean: str
    marked: str
    width: int
    height: int
    psnr_db: float
    changed_pixel_fraction: float
    difference_min: float
    difference_max: float
    channel_mean: tuple[float, float, float]
    channel_std: tuple[float, float, float]


@dataclass(frozen=True)
class ImageScore:
    """Single-image phase alignment against a discovered template."""

    path: str
    phase_mean: float
    phase_weighted: float
    channel_phase_weighted: tuple[float, float, float]
    top_two_channel_phase_12: float
    peak_count: int


def load_rgb(path: Path) -> np.ndarray:
    """Load PATH as float64 RGB pixels."""
    with Image.open(path) as image:
        return np.asarray(image.convert("RGB"), dtype=np.float64)


def _resize_float(channel: np.ndarray, size: int) -> np.ndarray:
    """Resize one floating-point channel without quantizing the residual."""
    image = Image.fromarray(channel.astype(np.float32), mode="F")
    return np.asarray(image.resize((size, size), Image.Resampling.BILINEAR), dtype=np.float64)


def pair_residual(clean: Path, marked: Path, *, size: int = 512) -> tuple[np.ndarray, PairMeasurement]:
    """Return a canonical RGB residual and measurements for an exact pair."""
    clean_rgb = load_rgb(clean)
    marked_rgb = load_rgb(marked)
    if clean_rgb.shape != marked_rgb.shape:
        raise ValueError(f"pair shapes differ: {clean_rgb.shape} != {marked_rgb.shape}")

    difference = marked_rgb - clean_rgb
    mse = float(np.mean(np.square(difference)))
    psnr = float("inf") if mse == 0.0 else float(20.0 * np.log10(255.0 / np.sqrt(mse)))
    residual = np.stack([_resize_float(difference[:, :, channel], size) for channel in range(3)], axis=2)
    measurement = PairMeasurement(
        clean=str(clean),
        marked=str(marked),
        width=int(clean_rgb.shape[1]),
        height=int(clean_rgb.shape[0]),
        psnr_db=psnr,
        changed_pixel_fraction=float(np.mean(np.any(difference != 0.0, axis=2))),
        difference_min=float(np.min(difference)),
        difference_max=float(np.max(difference)),
        channel_mean=tuple(float(value) for value in np.mean(difference, axis=(0, 1))),
        channel_std=tuple(float(value) for value in np.std(difference, axis=(0, 1))),
    )
    return residual, measurement


def normalized_channels(residual: np.ndarray) -> np.ndarray:
    """Zero-center and unit-normalize each residual channel."""
    centered = residual - np.mean(residual, axis=(0, 1), keepdims=True)
    norms = np.linalg.norm(centered, axis=(0, 1), keepdims=True)
    return np.divide(centered, norms, out=np.zeros_like(centered), where=norms != 0.0)


def channel_ncc(first: np.ndarray, second: np.ndarray) -> tuple[float, float, float]:
    """Return per-channel normalized cross-correlation."""
    first_norm = normalized_channels(first)
    second_norm = normalized_channels(second)
    values = np.sum(first_norm * second_norm, axis=(0, 1))
    return tuple(float(value) for value in values)


def build_template(residuals: list[np.ndarray]) -> np.ndarray:
    """Average canonical residuals after per-channel normalization."""
    if not residuals:
        raise ValueError("at least one residual is required")
    shape = residuals[0].shape
    if any(residual.shape != shape for residual in residuals):
        raise ValueError("all canonical residuals must have the same shape")
    return np.mean([normalized_channels(residual) for residual in residuals], axis=0)


def _template_fft(template: np.ndarray) -> np.ndarray:
    """Return a centered two-dimensional FFT for each RGB channel."""
    return np.fft.fftshift(np.fft.fft2(template, axes=(0, 1)), axes=(0, 1))


def select_peaks(
    template: np.ndarray,
    *,
    count: int = 64,
    min_radius: float = 8.0,
    max_radius_fraction: float = 0.35,
    min_distance: float = 3.0,
) -> np.ndarray:
    """Select separated high-energy carrier bins from one Fourier half-plane."""
    if count <= 0:
        raise ValueError("count must be positive")
    height, width, channels = template.shape
    if height != width or channels != 3:
        raise ValueError("template must be a square RGB array")
    center = height // 2
    spectrum = _template_fft(template)
    magnitude = np.linalg.norm(spectrum, axis=2)
    yy, xx = np.ogrid[:height, :width]
    radius = np.sqrt(np.square(yy - center) + np.square(xx - center))
    valid = (radius >= min_radius) & (radius <= height * max_radius_fraction)
    candidates = np.flatnonzero(valid)
    order = candidates[np.argsort(magnitude.ravel()[candidates])[::-1]]

    selected: list[tuple[int, int]] = []
    for flat_index in order:
        row, column = np.unravel_index(flat_index, magnitude.shape)
        dy, dx = int(row - center), int(column - center)
        if dy < 0 or (dy == 0 and dx < 0):
            continue
        if any((dy - old_dy) ** 2 + (dx - old_dx) ** 2 < min_distance**2 for old_dy, old_dx in selected):
            continue
        selected.append((dy, dx))
        if len(selected) == count:
            break
    if len(selected) != count:
        raise ValueError(f"could select only {len(selected)} of {count} peaks")
    return np.asarray(selected, dtype=np.int32)


def _high_pass_rgb(path: Path, size: int, blur_radius: float) -> np.ndarray:
    """Decode, resize, and subtract a small Gaussian blur from RGB pixels."""
    with Image.open(path) as source:
        image = source.convert("RGB").resize((size, size), Image.Resampling.LANCZOS)
    pixels = np.asarray(image, dtype=np.float64)
    blurred = np.asarray(image.filter(ImageFilter.GaussianBlur(radius=blur_radius)), dtype=np.float64)
    return pixels - blurred


def score_image(path: Path, template: np.ndarray, peaks: np.ndarray, *, blur_radius: float = 2.0) -> ImageScore:
    """Score one image by phase alignment at discovered carrier bins."""
    size = int(template.shape[0])
    image_fft = np.fft.fftshift(np.fft.fft2(_high_pass_rgb(path, size, blur_radius), axes=(0, 1)), axes=(0, 1))
    template_fft = _template_fft(template)
    center = size // 2
    phase_values: list[np.ndarray] = []
    weights: list[np.ndarray] = []
    for dy, dx in peaks:
        image_value = image_fft[center + int(dy), center + int(dx)]
        template_value = template_fft[center + int(dy), center + int(dx)]
        phase = np.real(image_value * np.conj(template_value)) / (np.abs(image_value) * np.abs(template_value) + 1e-12)
        phase_values.append(phase)
        weights.append(np.abs(template_value))
    phases = np.asarray(phase_values)
    carrier_weights = np.asarray(weights)
    channel_weighted = np.sum(phases * carrier_weights, axis=0) / np.sum(carrier_weights, axis=0)
    consensus_count = min(12, len(peaks))
    consensus_channels = np.sum(phases[:consensus_count] * carrier_weights[:consensus_count], axis=0) / np.sum(
        carrier_weights[:consensus_count], axis=0
    )
    top_two_channel_phase_12 = float(np.mean(np.sort(consensus_channels)[-2:]))
    return ImageScore(
        path=str(path),
        phase_mean=float(np.mean(phases)),
        phase_weighted=float(np.sum(phases * carrier_weights) / np.sum(carrier_weights)),
        channel_phase_weighted=tuple(float(value) for value in channel_weighted),
        top_two_channel_phase_12=top_two_channel_phase_12,
        peak_count=len(peaks),
    )


def save_template(path: Path, template: np.ndarray, peaks: np.ndarray) -> None:
    """Store a template in a pickle-free compressed NPZ artifact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, template=template.astype(np.float32), peaks=peaks.astype(np.int32))


def load_template(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Load a template artifact without enabling pickle."""
    with np.load(path, allow_pickle=False) as artifact:
        template = np.asarray(artifact["template"], dtype=np.float64)
        peaks = np.asarray(artifact["peaks"], dtype=np.int32)
    if template.ndim != 3 or template.shape[2] != 3 or template.shape[0] != template.shape[1]:
        raise ValueError("invalid template shape")
    if peaks.ndim != 2 or peaks.shape[1] != 2:
        raise ValueError("invalid peak shape")
    return template, peaks


def discovery_report(
    residuals: list[np.ndarray], measurements: list[PairMeasurement], peaks: np.ndarray
) -> dict[str, object]:
    """Build a JSON-safe report with pair statistics and cross-pair NCC."""
    pairwise = [
        {
            "first": measurements[first].marked,
            "second": measurements[second].marked,
            "channel_ncc": channel_ncc(residuals[first], residuals[second]),
        }
        for first, second in combinations(range(len(residuals)), 2)
    ]
    return {
        "pair_count": len(measurements),
        "pairs": [asdict(measurement) for measurement in measurements],
        "pairwise": pairwise,
        "peaks": peaks.tolist(),
    }


@click.group()
def main() -> None:
    """Discover and score an experimental shared spectral carrier."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")


@main.command()
@click.option(
    "--pair",
    "pairs",
    type=(
        click.Path(exists=True, dir_okay=False, path_type=Path),
        click.Path(exists=True, dir_okay=False, path_type=Path),
    ),
    multiple=True,
    required=True,
    help="Exact CLEAN MARKED pair; repeat for multiple pairs.",
)
@click.option("--size", type=click.IntRange(min=64), default=512, show_default=True)
@click.option("--peak-count", type=click.IntRange(min=1), default=64, show_default=True)
@click.option("--template-out", type=click.Path(dir_okay=False, path_type=Path), required=True)
@click.option("--report-out", type=click.Path(dir_okay=False, path_type=Path), required=True)
def discover(
    pairs: tuple[tuple[Path, Path], ...],
    size: int,
    peak_count: int,
    template_out: Path,
    report_out: Path,
) -> None:
    """Build a template and report from exact CLEAN MARKED pairs."""
    residuals: list[np.ndarray] = []
    measurements: list[PairMeasurement] = []
    for clean, marked in pairs:
        residual, measurement = pair_residual(clean, marked, size=size)
        residuals.append(residual)
        measurements.append(measurement)
    template = build_template(residuals)
    peaks = select_peaks(template, count=peak_count)
    save_template(template_out, template, peaks)
    report = discovery_report(residuals, measurements, peaks)
    report_out.parent.mkdir(parents=True, exist_ok=True)
    report_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    log.info("Wrote template: %s", template_out)
    log.info("Wrote report: %s", report_out)


@main.command()
@click.argument("template_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("images", nargs=-1, required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--report-out", type=click.Path(dir_okay=False, path_type=Path))
def score(template_path: Path, images: tuple[Path, ...], report_out: Path | None) -> None:
    """Score IMAGES against TEMPLATE_PATH."""
    template, peaks = load_template(template_path)
    scores = [asdict(score_image(image, template, peaks)) for image in images]
    payload = {"template": str(template_path), "scores": scores}
    rendered = json.dumps(payload, indent=2) + "\n"
    if report_out is None:
        log.info("%s", rendered.rstrip())
        return
    report_out.parent.mkdir(parents=True, exist_ok=True)
    report_out.write_text(rendered, encoding="utf-8")
    log.info("Wrote score report: %s", report_out)


if __name__ == "__main__":
    main()

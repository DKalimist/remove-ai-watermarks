"""Independently evaluate a numeric reverse-SynthID V3 NPZ codebook.

The loader accepts only the documented numeric format-v2 arrays and disables
pickle. It does not import or execute third-party code. Scores are exploratory:
the external reference provenance and labels still require independent oracle
validation before this can support a SynthID detector claim.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

import click
import numpy as np
from PIL import Image

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class V3CarrierModel:
    """Selected numeric bins from one exact-resolution V3 profile."""

    height: int
    width: int
    rows: np.ndarray
    columns: np.ndarray
    channels: np.ndarray
    phases: np.ndarray
    weights: np.ndarray
    expected_magnitudes: np.ndarray


@dataclass(frozen=True)
class V3Score:
    """Phase-alignment scores for one image."""

    path: str
    phase_score: float
    axial_phase_score: float
    active_weight_fraction: float
    peak_count: int


def _load_sparse_channel(artifact: np.lib.npyio.NpzFile, prefix: str, channel: int) -> tuple[np.ndarray, ...]:
    """Load one sparse channel without reconstructing full image-sized arrays."""
    indices = np.asarray(artifact[f"{prefix}idx_{channel}"], dtype=np.uint32)
    magnitudes = np.exp2(np.asarray(artifact[f"{prefix}mag_{channel}"], dtype=np.float64)) - 1.0
    phases = np.asarray(artifact[f"{prefix}phase_{channel}"], dtype=np.float64)
    coherence = np.asarray(artifact[f"{prefix}cons_{channel}"], dtype=np.float64) / 255.0
    if not (indices.shape == magnitudes.shape == phases.shape == coherence.shape):
        raise ValueError("sparse profile arrays have inconsistent shapes")
    return indices, magnitudes, phases, coherence


def load_v3_model(
    path: Path,
    *,
    height: int,
    width: int,
    peak_count: int = 256,
    min_radius: float = 15.0,
) -> V3CarrierModel:
    """Load top phase-consistent bins from a numeric V3 codebook profile."""
    prefix = f"{height}x{width}/"
    half_width = width // 2 + 1
    candidates: list[tuple[float, int, int, int, float, float]] = []
    with np.load(path, allow_pickle=False) as artifact:
        if int(artifact["format_version"]) != 2:
            raise ValueError("only numeric V3 format version 2 is supported")
        if not bool(int(artifact[f"{prefix}sparse"])):
            raise ValueError("only sparse profiles are supported by this audit loader")
        for channel in range(3):
            indices, magnitudes, phases, coherence = _load_sparse_channel(artifact, prefix, channel)
            rows, columns = np.unravel_index(indices, (height, half_width))
            signed_rows = np.where(rows > height // 2, rows - height, rows)
            radius = np.sqrt(np.square(signed_rows) + np.square(columns))
            valid = (radius >= min_radius) & (columns > 0)
            selection = np.square(coherence) * np.log1p(magnitudes)
            for index in np.flatnonzero(valid):
                candidates.append(
                    (
                        float(selection[index]),
                        int(rows[index]),
                        int(columns[index]),
                        channel,
                        float(phases[index]),
                        float(magnitudes[index]),
                    )
                )
    if len(candidates) < peak_count:
        raise ValueError(f"profile exposes only {len(candidates)} eligible bins")
    selected = sorted(candidates, reverse=True)[:peak_count]
    raw_weights = np.asarray([item[0] for item in selected], dtype=np.float64)
    return V3CarrierModel(
        height=height,
        width=width,
        rows=np.asarray([item[1] for item in selected], dtype=np.int32),
        columns=np.asarray([item[2] for item in selected], dtype=np.int32),
        channels=np.asarray([item[3] for item in selected], dtype=np.int8),
        phases=np.asarray([item[4] for item in selected], dtype=np.float64),
        weights=raw_weights / np.sum(raw_weights),
        expected_magnitudes=np.asarray([item[5] for item in selected], dtype=np.float64),
    )


def _load_profile_rgb(path: Path, model: V3CarrierModel) -> np.ndarray:
    """Load PATH and resize only when it does not match the profile geometry."""
    with Image.open(path) as source:
        image = source.convert("RGB")
        if image.size != (model.width, model.height):
            image = image.resize((model.width, model.height), Image.Resampling.LANCZOS)
        return np.asarray(image, dtype=np.float64)


def score_image(path: Path, model: V3CarrierModel) -> V3Score:
    """Score PATH against selected V3 phase bins."""
    pixels = _load_profile_rgb(path, model)
    values = np.empty(len(model.rows), dtype=np.complex128)
    for channel in range(3):
        positions = np.flatnonzero(model.channels == channel)
        if len(positions) == 0:
            continue
        spectrum = np.fft.fft2(pixels[:, :, channel])
        values[positions] = spectrum[model.rows[positions], model.columns[positions]]
    phase_difference = np.angle(values) - model.phases
    magnitude_gate = np.minimum(np.abs(values) / (model.expected_magnitudes + 1e-12), 1.0)
    active_weights = model.weights * magnitude_gate
    active_weight = float(np.sum(active_weights))
    if active_weight == 0.0:
        phase_score = 0.0
        axial_score = 0.0
    else:
        phase_score = float(np.sum(active_weights * np.cos(phase_difference)) / active_weight)
        axial_score = float(np.sum(active_weights * np.cos(2.0 * phase_difference)) / active_weight)
    return V3Score(
        path=str(path),
        phase_score=phase_score,
        axial_phase_score=axial_score,
        active_weight_fraction=active_weight,
        peak_count=len(model.rows),
    )


@click.command()
@click.argument("codebook", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("images", nargs=-1, required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--height", type=click.IntRange(min=64), required=True)
@click.option("--width", type=click.IntRange(min=64), required=True)
@click.option("--peak-count", type=click.IntRange(min=1), default=256, show_default=True)
@click.option("--report-out", type=click.Path(dir_okay=False, path_type=Path), required=True)
def main(codebook: Path, images: tuple[Path, ...], height: int, width: int, peak_count: int, report_out: Path) -> None:
    """Score IMAGES against one exact-resolution profile from CODEBOOK."""
    model = load_v3_model(codebook, height=height, width=width, peak_count=peak_count)
    payload = {
        "codebook": str(codebook),
        "height": height,
        "width": width,
        "peak_count": peak_count,
        "scores": [asdict(score_image(image, model)) for image in images],
    }
    report_out.parent.mkdir(parents=True, exist_ok=True)
    report_out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    log.info("Wrote V3 score report: %s", report_out)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()

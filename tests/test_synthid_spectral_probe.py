"""Synthetic tests for the paired SynthID spectral research harness."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import synthid_spectral_probe as probe


def _carrier(height: int, width: int) -> np.ndarray:
    yy, xx = np.mgrid[:height, :width]
    channels = [
        np.cos(2 * np.pi * (14 * xx / width + 14 * yy / height)),
        1.3 * np.cos(2 * np.pi * (14 * xx / width + 14 * yy / height) + 0.2),
        0.8 * np.cos(2 * np.pi * (14 * xx / width + 14 * yy / height) - 0.3),
    ]
    return np.stack(channels, axis=2)


def _write_pair(tmp_path: Path, name: str, shape: tuple[int, int], base: int) -> tuple[Path, Path]:
    height, width = shape
    yy, xx = np.mgrid[:height, :width]
    scene = base + 8 * np.sin(2 * np.pi * xx / width) + 5 * np.cos(2 * np.pi * yy / height)
    clean = np.stack([scene, scene + 3, scene - 3], axis=2)
    marked = clean + _carrier(height, width)
    clean_path = tmp_path / f"{name}-clean.png"
    marked_path = tmp_path / f"{name}-marked.png"
    Image.fromarray(np.clip(np.rint(clean), 0, 255).astype(np.uint8)).save(clean_path)
    Image.fromarray(np.clip(np.rint(marked), 0, 255).astype(np.uint8)).save(marked_path)
    return clean_path, marked_path


def test_pair_residual_preserves_float_signal_across_shapes(tmp_path: Path):
    first = _write_pair(tmp_path, "first", (96, 96), 100)
    second = _write_pair(tmp_path, "second", (128, 80), 140)

    first_residual, first_measurement = probe.pair_residual(*first, size=64)
    second_residual, second_measurement = probe.pair_residual(*second, size=64)

    assert first_residual.shape == (64, 64, 3)
    assert first_measurement.changed_pixel_fraction > 0.2
    assert second_measurement.width == 80
    assert min(probe.channel_ncc(first_residual, second_residual)) > 0.75


def test_selected_peaks_find_injected_frequency(tmp_path: Path):
    pair = _write_pair(tmp_path, "pair", (96, 96), 100)
    residual, _ = probe.pair_residual(*pair, size=64)
    template = probe.build_template([residual])

    peaks = probe.select_peaks(template, count=4)

    assert any(abs(int(dy)) == 14 and abs(int(dx)) == 14 for dy, dx in peaks)


def test_marked_image_scores_above_clean_image(tmp_path: Path):
    pair = _write_pair(tmp_path, "pair", (128, 128), 100)
    residual, _ = probe.pair_residual(*pair, size=128)
    template = probe.build_template([residual])
    peaks = probe.select_peaks(template, count=8)

    clean_score = probe.score_image(pair[0], template, peaks)
    marked_score = probe.score_image(pair[1], template, peaks)

    assert marked_score.phase_weighted > clean_score.phase_weighted
    assert marked_score.top_two_channel_phase_12 > clean_score.top_two_channel_phase_12


def test_template_round_trip_does_not_use_pickle(tmp_path: Path):
    template = np.zeros((64, 64, 3), dtype=np.float64)
    template[1, 1] = (1.0, 2.0, 3.0)
    peaks = np.asarray([[1, 1], [2, 2]], dtype=np.int32)
    path = tmp_path / "template.npz"

    probe.save_template(path, template, peaks)
    loaded_template, loaded_peaks = probe.load_template(path)

    assert np.array_equal(loaded_template, template)
    assert np.array_equal(loaded_peaks, peaks)


def test_discovery_report_contains_cross_pair_ncc(tmp_path: Path):
    first = _write_pair(tmp_path, "first", (96, 96), 100)
    second = _write_pair(tmp_path, "second", (128, 80), 140)
    first_residual, first_measurement = probe.pair_residual(*first, size=64)
    second_residual, second_measurement = probe.pair_residual(*second, size=64)
    template = probe.build_template([first_residual, second_residual])
    peaks = probe.select_peaks(template, count=4)

    report = probe.discovery_report(
        [first_residual, second_residual],
        [first_measurement, second_measurement],
        peaks,
    )

    assert report["pair_count"] == 2
    assert len(report["pairwise"]) == 1

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import synthid_phase_carrier as carrier


def _write_image(path: Path, *, phase: float | None, seed: int) -> None:
    height = width = 64
    rng = np.random.default_rng(seed)
    pixels = 100.0 + rng.normal(0.0, 3.0, size=(height, width, 3))
    if phase is not None:
        yy, xx = np.mgrid[:height, :width]
        wave = 12.0 * np.cos(2.0 * np.pi * (7.0 * yy / height + 5.0 * xx / width) + phase)
        pixels += wave[:, :, None]
    Image.fromarray(np.clip(np.rint(pixels), 0, 255).astype(np.uint8), mode="RGB").save(path)


def test_discovered_model_separates_shared_phase_from_noise(tmp_path: Path) -> None:
    positives: list[Path] = []
    for index in range(4):
        path = tmp_path / f"positive-{index}.png"
        _write_image(path, phase=0.4, seed=index)
        positives.append(path)
    heldout = tmp_path / "heldout.png"
    negative = tmp_path / "negative.png"
    _write_image(heldout, phase=0.4, seed=10)
    _write_image(negative, phase=None, seed=11)

    model = carrier.discover_model(positives, peak_count=8, min_radius=1.0)

    assert carrier.score_image(heldout, model).score > carrier.score_image(negative, model).score


def test_leave_one_out_coherence_exposes_phase_outlier() -> None:
    units = np.asarray([1.0 + 0.0j, 1.0 + 0.0j, 1.0 + 0.0j, -1.0 + 0.0j])
    unit_sum = np.sum(units)

    coherences = [carrier._leave_one_out_coherence(unit_sum, unit, 4.0) for unit in units]

    assert min(coherences) == pytest.approx(1.0 / 3.0)
    assert max(coherences) == pytest.approx(1.0)


def test_model_round_trip_is_pickle_free(tmp_path: Path) -> None:
    positives: list[Path] = []
    for index in range(3):
        path = tmp_path / f"positive-{index}.png"
        _write_image(path, phase=0.4, seed=index)
        positives.append(path)
    model = carrier.discover_model(positives, peak_count=4, min_radius=1.0)
    artifact = tmp_path / "model.npz"

    carrier.save_model(artifact, model)
    loaded = carrier.load_model(artifact)

    assert loaded.height == model.height
    assert loaded.width == model.width
    assert np.array_equal(loaded.rows, model.rows)
    assert np.isclose(np.sum(loaded.weights), 1.0)


def test_candidate_bins_restrict_discovery(tmp_path: Path) -> None:
    positives: list[Path] = []
    for index in range(3):
        path = tmp_path / f"positive-{index}.png"
        _write_image(path, phase=0.4, seed=index)
        positives.append(path)
    bins = np.asarray([[7, 5, 0], [7, 5, 1], [7, 5, 2]], dtype=np.int32)

    model = carrier.discover_model(positives, peak_count=3, min_radius=1.0, candidate_bins=bins)

    actual = set(zip(model.rows.tolist(), model.columns.tolist(), model.channels.tolist(), strict=True))
    expected = set(map(tuple, bins.tolist()))
    assert actual == expected


def test_discovery_requires_three_images(tmp_path: Path) -> None:
    path = tmp_path / "positive.png"
    _write_image(path, phase=0.4, seed=1)

    with pytest.raises(ValueError, match="at least three"):
        carrier.discover_model([path, path], peak_count=4)


def test_scoring_rejects_geometry_mismatch(tmp_path: Path) -> None:
    positives: list[Path] = []
    for index in range(3):
        path = tmp_path / f"positive-{index}.png"
        _write_image(path, phase=0.4, seed=index)
        positives.append(path)
    model = carrier.discover_model(positives, peak_count=4, min_radius=1.0)
    mismatch = tmp_path / "mismatch.png"
    Image.new("RGB", (80, 64)).save(mismatch)

    with pytest.raises(ValueError, match="does not match"):
        carrier.score_image(mismatch, model)


def test_scoring_can_canonicalize_geometry(tmp_path: Path) -> None:
    positives: list[Path] = []
    for index in range(3):
        path = tmp_path / f"positive-{index}.png"
        _write_image(path, phase=0.4, seed=index)
        positives.append(path)
    model = carrier.discover_model(positives, peak_count=4, min_radius=1.0)
    mismatch = tmp_path / "mismatch.png"
    Image.new("RGB", (80, 64), color=(100, 100, 100)).save(mismatch)

    score = carrier.score_image(mismatch, model, canonicalize_geometry=True)

    assert score.path == str(mismatch)
    assert score.peak_count == 4

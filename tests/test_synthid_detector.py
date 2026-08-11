"""Runtime tests for the positive-only SynthID periodic carrier detector."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

import remove_ai_watermarks.synthid_detector as detector


@pytest.fixture(scope="module")
def supported_images(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """Create supported-geometry positive and negative synthetic fixtures."""
    directory = tmp_path_factory.mktemp("synthid-detector")
    template, *_model = detector._load_template()
    scaled_tile = np.rint(template / np.max(np.abs(template)))
    marked = np.full((detector.MODEL_HEIGHT, detector.MODEL_WIDTH, 3), 128, dtype=np.float64)
    marked += np.tile(scaled_tile, (128, 128, 1))

    positive = directory / "positive.png"
    negative = directory / "negative.png"
    Image.fromarray(np.clip(np.rint(marked), 0, 255).astype(np.uint8), "RGB").save(positive)
    Image.new("RGB", (detector.MODEL_WIDTH, detector.MODEL_HEIGHT), (128, 128, 128)).save(negative)
    return positive, negative


def test_bundled_model_is_the_frozen_calibrated_artifact() -> None:
    model = Path(detector.__file__).parent / "assets" / detector.MODEL_FILENAME

    assert hashlib.sha256(model.read_bytes()).hexdigest() == (
        "ee7838da8542c206c3403284b68e98f0ac99429e82f262c1a438f50a638b488b"
    )


@pytest.mark.parametrize(
    ("width", "height"),
    [(1000, 1000), (1001, 1000), (3000, 6000), (768, 1364)],
)
def test_supported_geometry_uses_the_challenged_pixel_count_range(width: int, height: int) -> None:
    assert detector._geometry_supported(width, height)


@pytest.mark.parametrize(
    ("width", "height"),
    [(999, 1000), (3001, 6000), (64, 32)],
)
def test_geometry_outside_the_challenged_pixel_count_range_is_unsupported(
    width: int,
    height: int,
) -> None:
    assert not detector._geometry_supported(width, height)


def test_detects_supported_periodic_carrier(supported_images: tuple[Path, Path]) -> None:
    positive, _negative = supported_images

    result = detector.detect_synthid(positive)

    assert result.status == "detected"
    assert result.detected is True
    assert result.score is not None
    assert result.score > result.threshold
    assert result.to_dict()["detector"] == detector.DETECTOR_ID


def test_detects_unregistered_non_divisible_geometry_in_size_range(tmp_path: Path) -> None:
    width, height = 1001, 1000
    template, *_model = detector._load_template()
    scaled_tile = np.rint(template / np.max(np.abs(template)))
    repeats_y = (height + scaled_tile.shape[0] - 1) // scaled_tile.shape[0]
    repeats_x = (width + scaled_tile.shape[1] - 1) // scaled_tile.shape[1]
    carrier = np.tile(scaled_tile, (repeats_y, repeats_x, 1))[:height, :width]
    pixels = np.clip(np.rint(carrier + 128.0), 0, 255).astype(np.uint8)
    path = tmp_path / "non-divisible-positive.png"
    Image.fromarray(pixels, "RGB").save(path)

    result = detector.detect_synthid(path)

    assert result.status == "detected"
    assert (result.width, result.height) == (width, height)
    assert result.score is not None
    assert result.score > result.threshold


def test_supported_negative_does_not_claim_clean(supported_images: tuple[Path, Path]) -> None:
    _positive, negative = supported_images

    result = detector.detect_synthid(negative)

    assert result.status == "not_detected"
    assert result.detected is False
    assert result.score == pytest.approx(0.0)


def test_threshold_mutation_changes_the_real_verdict(
    monkeypatch: pytest.MonkeyPatch,
    supported_images: tuple[Path, Path],
) -> None:
    positive, _negative = supported_images
    baseline = detector.detect_synthid(positive)
    assert baseline.score is not None
    assert baseline.status == "detected"
    mutated_threshold = float(np.nextafter(baseline.score, np.inf))
    assert mutated_threshold > baseline.score

    monkeypatch.setattr(detector, "TILE_THRESHOLD", mutated_threshold)
    mutated = detector.detect_synthid(positive)

    assert mutated.status == "not_detected"
    assert mutated.threshold == mutated_threshold


def test_unsupported_geometry_is_distinct_from_negative(tmp_path: Path) -> None:
    path = tmp_path / "small.png"
    Image.new("RGB", (64, 32), "white").save(path)

    result = detector.detect_synthid(path)

    assert result.status == "unsupported"
    assert result.score is None
    assert (result.width, result.height) == (64, 32)


def test_shared_bgr_decode_matches_file_decode(supported_images: tuple[Path, Path]) -> None:
    import cv2

    positive, _negative = supported_images
    bgr = cv2.imread(str(positive))
    assert bgr is not None

    from_file = detector.detect_synthid(positive)
    from_array = detector.detect_synthid(positive, image=bgr)

    assert from_array == from_file


def test_supported_geometry_requires_pixel_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    supported_images: tuple[Path, Path],
) -> None:
    _positive, negative = supported_images
    monkeypatch.setattr(detector, "is_available", lambda: False)

    with pytest.raises(RuntimeError, match="pixel extra"):
        detector.detect_synthid(negative)


def test_fold_accepts_non_divisible_geometry_without_resampling() -> None:
    rng = np.random.default_rng(20260810)
    tile = rng.normal(0.0, 8.0, size=(16, 16, 3))
    repeated = np.tile(tile, (19, 20, 1)) + 128.0

    divisible = detector.fold_residual_template(
        repeated,
        tile_height=16,
        tile_width=16,
        denoise_sigma=1.0,
    )
    non_divisible = detector.fold_residual_template(
        repeated[:299, :317],
        tile_height=16,
        tile_width=16,
        denoise_sigma=1.0,
    )
    divisible_unit, _ = detector.unit_tile(divisible)
    non_divisible_unit, _ = detector.unit_tile(non_divisible)

    assert non_divisible.shape == (16, 16, 3)
    assert float(np.sum(divisible_unit * non_divisible_unit)) > 0.999


def test_non_divisible_fold_matches_modulo_cell_means() -> None:
    import cv2

    rng = np.random.default_rng(44041)
    pixels = rng.integers(0, 256, size=(53, 71, 3), dtype=np.uint8)
    source = pixels.astype(np.float32)
    residual = source - cv2.GaussianBlur(
        source,
        (0, 0),
        sigmaX=1.25,
        sigmaY=1.25,
        borderType=cv2.BORDER_REFLECT_101,
    )
    expected = np.empty((16, 16, 3), dtype=np.float64)
    for tile_y in range(16):
        for tile_x in range(16):
            expected[tile_y, tile_x] = residual[tile_y::16, tile_x::16].mean(
                axis=(0, 1),
                dtype=np.float64,
            )
    expected -= np.mean(expected, axis=(0, 1), keepdims=True)

    actual = detector.fold_residual_template(
        pixels,
        tile_height=16,
        tile_width=16,
        denoise_sigma=1.25,
    )

    np.testing.assert_allclose(actual, expected, rtol=0.0, atol=0.0)


def test_fold_rejects_tile_larger_than_image() -> None:
    pixels = np.zeros((15, 16, 3), dtype=np.uint8)

    with pytest.raises(ValueError, match="at least as large"):
        detector.fold_residual_template(
            pixels,
            tile_height=16,
            tile_width=16,
            denoise_sigma=1.0,
        )

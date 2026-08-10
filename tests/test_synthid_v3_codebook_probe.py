from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import synthid_v3_codebook_probe as probe


def _write_codebook(path: Path, *, height: int, width: int, phase: float) -> None:
    half_width = width // 2 + 1
    rows = np.asarray([7, 11, 13, 17], dtype=np.uint32)
    columns = np.asarray([5, 9, 12, 15], dtype=np.uint32)
    indices = np.ravel_multi_index((rows, columns), (height, half_width)).astype(np.uint32)
    payload: dict[str, np.ndarray] = {
        "format_version": np.asarray(2),
        f"{height}x{width}/sparse": np.asarray(1),
    }
    for channel in range(3):
        payload[f"{height}x{width}/idx_{channel}"] = indices
        magnitudes = np.asarray([1000.0, 10.0, 10.0, 10.0])
        payload[f"{height}x{width}/mag_{channel}"] = np.log2(1.0 + magnitudes).astype(np.float16)
        payload[f"{height}x{width}/phase_{channel}"] = np.full(4, phase, dtype=np.float16)
        payload[f"{height}x{width}/cons_{channel}"] = np.full(4, 255, dtype=np.uint8)
    np.savez(path, **payload)


def _write_carrier(path: Path, *, height: int, width: int, phase: float) -> None:
    yy, xx = np.mgrid[:height, :width]
    carrier = 80.0 + 20.0 * np.cos(2.0 * np.pi * (7.0 * yy / height + 5.0 * xx / width) + phase)
    pixels = np.repeat(carrier[:, :, None], 3, axis=2)
    Image.fromarray(np.clip(np.rint(pixels), 0, 255).astype(np.uint8), mode="RGB").save(path)


def test_numeric_codebook_scores_matching_phase(tmp_path: Path) -> None:
    height = width = 64
    codebook = tmp_path / "codebook.npz"
    image = tmp_path / "image.png"
    _write_codebook(codebook, height=height, width=width, phase=0.4)
    _write_carrier(image, height=height, width=width, phase=0.4)

    model = probe.load_v3_model(codebook, height=height, width=width, peak_count=4, min_radius=1.0)
    score = probe.score_image(image, model)

    assert score.peak_count == 4
    assert score.phase_score > 0.0


def test_rejects_wrong_format(tmp_path: Path) -> None:
    artifact = tmp_path / "bad.npz"
    np.savez(artifact, format_version=np.asarray(1))

    with pytest.raises(ValueError, match="version 2"):
        probe.load_v3_model(artifact, height=64, width=64)

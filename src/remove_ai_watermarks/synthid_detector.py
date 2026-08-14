"""Detect the confirmed periodic SynthID image carrier at calibrated image sizes.

This is a positive-only detector for one measured carrier epoch, not Google's
private payload decoder. A positive result is strong local evidence for the
carrier. A negative result means only that the selected detector did not find
it; image sizes outside that mode's calibrated range are reported separately.

The numeric runtime requires the ``pixels`` extra. Imports remain lazy so the
package's metadata-only paths stay dependency-light.
"""

# The optional numeric libraries do not provide complete types for this path.
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from numpy.typing import NDArray

SynthIDDetectionStatus = Literal["detected", "not_detected", "unsupported"]

DETECTOR_ID = "synthid-periodic-tile-v2"
REGISTERED_DETECTOR_ID = "synthid-periodic-tile-registered-v2"
LARGE_DETECTOR_ID = "synthid-periodic-tile-large-v1"
MODEL_FILENAME = "synthid_periodic_tile_2048_v1.npz"
# The template remains frozen at this model geometry. Runtime images are never
# resized. The supported pixel-count interval is the separately challenged domain:
# below it too few repetitions make the positive-only statistic unreliable, and
# above it resource use and specificity have not been calibrated.
MODEL_WIDTH = 2048
MODEL_HEIGHT = 2048
MIN_SUPPORTED_PIXELS = 1_000_000
MAX_SUPPORTED_PIXELS = 18_000_000
TILE_THRESHOLD = 0.17357069773071196
REGISTERED_MIN_SUPPORTED_PIXELS = 250_000
REGISTERED_MAX_SUPPORTED_PIXELS = 10_000_000
REGISTERED_MIN_SIDE = 64
# The registered score is the minimum normalized margin across its amplitude,
# spectral-candidate, and high-frequency agreement gates.
REGISTERED_THRESHOLD = 1.0
# The large-image score combines all-window fixed and spatial opponent gates
# with an any-window signed opponent mid-band gate. The one vulnerable portrait
# geometry has an additional Green mid-band upper gate.
LARGE_THRESHOLD = 1.0
LARGE_MIN_PIXELS = 10_000_000
LARGE_MAX_PIXELS = 18_000_000
LARGE_WINDOW = 2_048
LARGE_PHASE = 16
LARGE_FIXED_SCORE_MIN = 0.14
LARGE_RED_GREEN_SPATIAL_MIN = 0.90
LARGE_BLUE_YELLOW_SPATIAL_MIN = 0.70
LARGE_BLUE_YELLOW_MID_BAND_MAX = -0.15
LARGE_PORTRAIT_GEOMETRY = (3_072, 5_504)
LARGE_PORTRAIT_GREEN_MID_BAND_MAX = 0.06
INSTALL_HINT = "install the pixel extra: uv add 'remove-ai-watermarks[pixels]'"


@dataclass(frozen=True)
class SynthIDDetection:
    """One local periodic-carrier verdict."""

    status: SynthIDDetectionStatus
    width: int
    height: int
    score: float | None
    threshold: float
    detector: str = DETECTOR_ID

    @property
    def detected(self) -> bool:
        """Whether the supported carrier crossed its frozen threshold."""
        return self.status == "detected"

    def to_dict(self) -> dict[str, str | int | float | None]:
        """Return a JSON-safe result without a local file path."""
        return {
            "status": self.status,
            "width": self.width,
            "height": self.height,
            "score": self.score,
            "threshold": self.threshold,
            "detector": self.detector,
        }


@dataclass(frozen=True)
class LargeImageComponents:
    """Auditable margins for the calibrated large-image carrier branch."""

    width: int
    height: int
    minimum_fixed_score: float
    minimum_red_green_spatial: float
    minimum_blue_yellow_spatial: float
    minimum_blue_yellow_mid_band: float
    maximum_green_mid_band: float

    @property
    def decision_score(self) -> float:
        """Return the minimum normalized gate margin; one is the boundary."""
        margins = [
            self.minimum_fixed_score / LARGE_FIXED_SCORE_MIN,
            self.minimum_red_green_spatial / LARGE_RED_GREEN_SPATIAL_MIN,
            self.minimum_blue_yellow_spatial / LARGE_BLUE_YELLOW_SPATIAL_MIN,
            self.minimum_blue_yellow_mid_band / LARGE_BLUE_YELLOW_MID_BAND_MAX,
        ]
        if (self.width, self.height) == LARGE_PORTRAIT_GEOMETRY:
            margins.append(1.0 + LARGE_PORTRAIT_GREEN_MID_BAND_MAX - self.maximum_green_mid_band)
        return min(margins)


def is_available() -> bool:
    """True when the optional numeric runtime is installed."""
    from remove_ai_watermarks.optional_deps import module_available

    return module_available("cv2", "numpy")


@lru_cache(maxsize=1)
def _load_template() -> tuple[NDArray[Any], float, int, int, int, int]:
    """Load and validate the bundled pickle-free detector model."""
    import numpy as np

    model_path = Path(__file__).parent / "assets" / MODEL_FILENAME
    with np.load(model_path, allow_pickle=False) as artifact:
        if int(artifact["format_version"]) != 1:
            raise RuntimeError("unsupported SynthID detector model format")
        height = int(artifact["height"])
        width = int(artifact["width"])
        tile_height = int(artifact["tile_height"])
        tile_width = int(artifact["tile_width"])
        denoise_sigma = float(artifact["denoise_sigma"])
        template = np.asarray(artifact["template"], dtype=np.float64)
    if not _geometry_supported(width, height):
        raise RuntimeError("bundled SynthID detector has unexpected geometry")
    if template.shape != (tile_height, tile_width, 3):
        raise RuntimeError("bundled SynthID detector has an invalid template shape")
    if not np.all(np.isfinite(template)) or not np.isclose(np.linalg.norm(template), 1.0):
        raise RuntimeError("bundled SynthID detector has an invalid template")
    if not np.isfinite(denoise_sigma) or denoise_sigma <= 0.0:
        raise RuntimeError("bundled SynthID detector has an invalid denoise sigma")
    return template, denoise_sigma, height, width, tile_height, tile_width


def fold_residual_template(
    pixels: NDArray[Any],
    *,
    tile_height: int,
    tile_width: int,
    denoise_sigma: float,
) -> NDArray[Any]:
    """Estimate a zero-mean periodic residual template by modulo folding."""
    import cv2
    import numpy as np

    if pixels.ndim != 3 or pixels.shape[2] != 3:
        raise ValueError("pixels must have shape (height, width, 3)")
    if tile_height < 1 or tile_width < 1 or denoise_sigma <= 0.0:
        raise ValueError("tile dimensions and denoise sigma must be positive")
    height, width = pixels.shape[:2]
    if height < tile_height or width < tile_width:
        raise ValueError("image geometry must be at least as large as the tile geometry")
    divisible = height % tile_height == 0 and width % tile_width == 0
    full_height = height - height % tile_height
    full_width = width - width % tile_width
    repeats_y = full_height // tile_height
    repeats_x = full_width // tile_width
    remaining_height = height - full_height
    remaining_width = width - full_width
    counts = np.full((tile_height, tile_width), repeats_y * repeats_x, dtype=np.int64)
    counts[:remaining_height] += repeats_x
    counts[:, :remaining_width] += repeats_y
    counts[:remaining_height, :remaining_width] += 1

    # OpenCV filters channels independently. Processing one channel at a time
    # keeps the 18 MP upper bound from requiring two full three-channel float32
    # buffers in addition to the decoded image.
    folded = np.empty((tile_height, tile_width, 3), dtype=np.float64)
    for channel in range(3):
        residual = pixels[:, :, channel].astype(np.float32)
        residual -= cv2.GaussianBlur(
            residual,
            (0, 0),
            sigmaX=denoise_sigma,
            sigmaY=denoise_sigma,
            borderType=cv2.BORDER_REFLECT_101,
        )
        if divisible:
            folded[:, :, channel] = residual.reshape(
                repeats_y,
                tile_height,
                repeats_x,
                tile_width,
            ).mean(axis=(0, 2), dtype=np.float64)
            continue
        folded_sum = (
            residual[:full_height, :full_width]
            .reshape(
                repeats_y,
                tile_height,
                repeats_x,
                tile_width,
            )
            .sum(axis=(0, 2), dtype=np.float64)
        )
        if remaining_height:
            bottom = residual[full_height:, :full_width].reshape(
                remaining_height,
                repeats_x,
                tile_width,
            )
            folded_sum[:remaining_height] += bottom.sum(axis=1, dtype=np.float64)
        if remaining_width:
            right = residual[:full_height, full_width:].reshape(
                repeats_y,
                tile_height,
                remaining_width,
            )
            folded_sum[:, :remaining_width] += right.sum(axis=0, dtype=np.float64)
        if remaining_height and remaining_width:
            folded_sum[:remaining_height, :remaining_width] += residual[
                full_height:,
                full_width:,
            ]
        folded[:, :, channel] = folded_sum / counts
    return folded - np.mean(folded, axis=(0, 1), keepdims=True)


def unit_tile(tile: NDArray[Any]) -> tuple[NDArray[Any], float]:
    """Return TILE normalized by its L2 norm and the original norm."""
    import numpy as np

    norm = float(np.linalg.norm(tile))
    if norm == 0.0:
        return np.zeros_like(tile, dtype=np.float64), 0.0
    return np.asarray(tile, dtype=np.float64) / norm, norm


def _image_size(image_path: Path) -> tuple[int, int]:
    from PIL import Image

    with Image.open(image_path) as image:
        return image.size


def _geometry_supported(width: int, height: int) -> bool:
    """Whether the image has a calibrated number of periodic-tile samples."""
    pixels = width * height
    return MIN_SUPPORTED_PIXELS <= pixels <= MAX_SUPPORTED_PIXELS


def _registered_geometry_supported(width: int, height: int) -> bool:
    """Whether scale registration was challenged at this decoded size."""
    pixels = width * height
    return (
        min(width, height) >= REGISTERED_MIN_SIDE
        and REGISTERED_MIN_SUPPORTED_PIXELS <= pixels <= REGISTERED_MAX_SUPPORTED_PIXELS
    )


def _large_geometry_supported(width: int, height: int) -> bool:
    """Whether fixed phase-aligned windows cover the calibrated large range."""
    pixels = width * height
    return min(width, height) >= LARGE_WINDOW and LARGE_MIN_PIXELS < pixels <= LARGE_MAX_PIXELS


def folded_template_score(
    pixels: NDArray[Any],
    template: NDArray[Any],
    denoise_sigma: float,
) -> tuple[float, NDArray[Any]]:
    """Fold PIXELS at the model geometry and score the normalized tile."""
    tile_height, tile_width = template.shape[:2]
    folded = fold_residual_template(
        pixels,
        tile_height=tile_height,
        tile_width=tile_width,
        denoise_sigma=denoise_sigma,
    )
    normalized, _norm = unit_tile(folded)
    return float((template * normalized).sum()), folded


def _large_window_starts(length: int) -> tuple[int, ...]:
    """Return phase-aligned starts that cover both edges without resampling."""
    if length < LARGE_WINDOW:
        raise ValueError("large-image sides must be at least 2,048 pixels")
    last = ((length - LARGE_WINDOW) // LARGE_PHASE) * LARGE_PHASE
    starts = list(range(0, last + 1, LARGE_WINDOW))
    if starts[-1] != last:
        starts.append(last)
    return tuple(starts)


def _correlation(left: NDArray[Any], right: NDArray[Any]) -> float:
    import numpy as np

    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    return float(np.real(np.vdot(right, left)) / denominator) if denominator > 0.0 else 0.0


def _large_window_components(
    folded: NDArray[Any],
    template: NDArray[Any],
) -> tuple[float, float, float, float]:
    """Measure the four color-phase features used by the large branch."""
    import numpy as np

    folded_red_green = folded[:, :, 0] - folded[:, :, 1]
    template_red_green = template[:, :, 0] - template[:, :, 1]
    folded_blue_yellow = folded[:, :, 2] - 0.5 * (folded[:, :, 0] + folded[:, :, 1])
    template_blue_yellow = template[:, :, 2] - 0.5 * (template[:, :, 0] + template[:, :, 1])

    height, width = folded.shape[:2]
    y_coordinates = np.minimum(np.arange(height), height - np.arange(height))
    x_coordinates = np.minimum(np.arange(width), width - np.arange(width))
    radius = np.sqrt(y_coordinates[:, None] ** 2 + x_coordinates[None, :] ** 2)
    mid_band = (radius >= 4.5) & (radius < 6.5)
    blue_yellow_mid = _correlation(
        np.fft.fft2(folded_blue_yellow)[mid_band],
        np.fft.fft2(template_blue_yellow)[mid_band],
    )
    green_mid = _correlation(
        np.fft.fft2(folded[:, :, 1])[mid_band],
        np.fft.fft2(template[:, :, 1])[mid_band],
    )
    return (
        _correlation(folded_red_green, template_red_green),
        _correlation(folded_blue_yellow, template_blue_yellow),
        blue_yellow_mid,
        green_mid,
    )


def large_image_components(
    pixels: NDArray[Any],
    template: NDArray[Any],
    denoise_sigma: float,
) -> LargeImageComponents:
    """Score all phase-aligned 2,048-pixel windows of one large RGB image."""
    if pixels.ndim != 3 or pixels.shape[2] != 3:
        raise ValueError("pixels must have shape (height, width, 3)")
    height, width = pixels.shape[:2]
    if not _large_geometry_supported(width, height):
        raise ValueError("image geometry is outside the calibrated large-image range")

    minimum_fixed = float("inf")
    minimum_red_green = float("inf")
    minimum_blue_yellow = float("inf")
    minimum_blue_yellow_mid = float("inf")
    maximum_green_mid = -float("inf")
    for y in _large_window_starts(height):
        for x in _large_window_starts(width):
            window = pixels[y : y + LARGE_WINDOW, x : x + LARGE_WINDOW]
            fixed_score, folded = folded_template_score(window, template, denoise_sigma)
            red_green, blue_yellow, blue_yellow_mid, green_mid = _large_window_components(
                folded,
                template,
            )
            minimum_fixed = min(minimum_fixed, fixed_score)
            minimum_red_green = min(minimum_red_green, red_green)
            minimum_blue_yellow = min(minimum_blue_yellow, blue_yellow)
            minimum_blue_yellow_mid = min(minimum_blue_yellow_mid, blue_yellow_mid)
            maximum_green_mid = max(maximum_green_mid, green_mid)
    return LargeImageComponents(
        width=width,
        height=height,
        minimum_fixed_score=minimum_fixed,
        minimum_red_green_spatial=minimum_red_green,
        minimum_blue_yellow_spatial=minimum_blue_yellow,
        minimum_blue_yellow_mid_band=minimum_blue_yellow_mid,
        maximum_green_mid_band=maximum_green_mid,
    )


def detect_synthid(
    image_path: str | Path,
    *,
    image: NDArray[Any] | None = None,
    register_scale: bool = False,
) -> SynthIDDetection:
    """Detect the supported periodic carrier in IMAGE_PATH.

    ``not_detected`` is not a clean-image guarantee. It means only that the
    frozen periodic carrier did not cross its calibrated threshold. Set
    ``register_scale`` for the slower, separately calibrated resize search.
    """
    path = Path(image_path)
    if image is None:
        width, height = _image_size(path)
    else:
        if image.ndim != 3 or image.shape[2] != 3:
            raise ValueError("image must be a three-channel BGR array")
        height, width = image.shape[:2]
    large_mode = not register_scale and width * height > LARGE_MIN_PIXELS
    if register_scale:
        geometry_supported = _registered_geometry_supported(width, height)
        threshold = REGISTERED_THRESHOLD
        detector_id = REGISTERED_DETECTOR_ID
    elif large_mode:
        geometry_supported = _large_geometry_supported(width, height)
        threshold = LARGE_THRESHOLD
        detector_id = LARGE_DETECTOR_ID
    else:
        geometry_supported = _geometry_supported(width, height)
        threshold = TILE_THRESHOLD
        detector_id = DETECTOR_ID
    if not geometry_supported:
        return SynthIDDetection(
            status="unsupported",
            width=width,
            height=height,
            score=None,
            threshold=threshold,
            detector=detector_id,
        )
    if not is_available():
        raise RuntimeError(f"SynthID pixel detection needs numpy and OpenCV; {INSTALL_HINT}")

    import numpy as np
    from PIL import Image

    template, sigma, *_model = _load_template()
    if image is None:
        with Image.open(path) as source:
            pixels = np.asarray(source.convert("RGB"), dtype=np.uint8)
    else:
        pixels = np.asarray(image[:, :, ::-1], dtype=np.uint8)
    if pixels.shape != (height, width, 3):
        raise RuntimeError("decoded image geometry does not match its header")
    if register_scale:
        from remove_ai_watermarks._synthid_registered import registered_score

        score = registered_score(pixels, template, sigma)
    elif large_mode:
        score = large_image_components(pixels, template, sigma).decision_score
    else:
        score, _folded = folded_template_score(pixels, template, sigma)
    return SynthIDDetection(
        status="detected" if score >= threshold else "not_detected",
        width=width,
        height=height,
        score=score,
        threshold=threshold,
        detector=detector_id,
    )

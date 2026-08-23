# SynthID local detector research

> Research archive for the hunt for a local, keyless SynthID pixel detector.
> Not a statement of current product capability. Shipped behavior:
> [supported signals](supported-signals.md) and
> [known limitations](known-limitations.md).
>
> Sister pages: [classifier models](synthid-classifiers.md),
> [SynthID mark removal](synthid-removal-research.md),
> [mechanism reference](synthid.md). Dated measurements live in the
> [chronological plan](synthid-detector-removal-plan.md).

## Result

The local OpenAI SynthID detector hunt closed 2026-08-20. Google has no
public payload decoder. Nothing in this project reproduces one.

The mark behaves like a keyed spread-spectrum residual: a content-adaptive
`x' = x + g(x)` with a paired decoder (DeepMind patent family, optional
secret in intermediate layers, encoder/decoder ensembles that do not
recognize each other). Without that pair, the residual sits under the
scene. Keyless energy, TrustMark transfer, L1 distillation, a flat-field
stamp, and a 16-32 band student all failed to read the official oracle
contrast on photographs.

What the product uses for the *watermark* is signed provenance and
`verify-openai-synthid`. The experimental pixel route in `identify` is
`pipeline_lattice`, a generation-pipeline ID, not SynthID. Lineage rates
for that route are in [classifier models](synthid-classifiers.md).

## Closed detector routes

| Route | Close | Why |
| --- | --- | --- |
| Keyless energy in 16-32 px | 2026-08-20 | L1 AUC 0.53; official decoder reads phase structure, not energy |
| TrustMark / open-encoder transfer | 2026-08-20 | E3 leave-one-encoder-out at chance on TrustMark (0.505 ridge, 0.510 conv) |
| L1 distillation of oracle bits | 2026-08-20 | Geometry-only AUC 0.78-0.83 beats pixel 124-d (0.64). ChatGPT export and `opened` C2PA predict `not_detected`. Inside 1254x1254, permutation p=0.45 |
| Flat 16-32 matched filter | 2026-08-21 | Leave-one-out residual correlation 0.645 on gray flats; 0.007-0.025 on COCO photo residuals. L1 AUC 0.70 was a size confound (size-matched 0.59 / 0.44) |
| `gpt-image-1` as encoder-off pair | 2026-08-21 | Does not stamp. `gpt-image-2` does |
| CNN on raw L1 bits | 2026-08-21 | Do not train. Labels are export geometry and presentation, not the mark |
| Origin-locked lattice as SynthID | 2026-08-16 | Two-pixel crop kills it; published SynthID keeps 99.97% TPR under aggressive crop. See classifiers for the honest `google_lineage_renderer` name |

Open: Google (no oracle); `chatgpt-image-latest` once the organization is
verified. A size-specific whitened 16-32 template on photographs is not
justified until amplitude is measured without the flat-arm G.

## Oracle and seeds

Official `POST /v1/content_provenance_checks`, metadata stripped, pixels
preserved. Raw files stay gitignored under
`.local-eval/synthid/prc-oklab-attack-2026-08-15/`.

| Seed | Path | Size |
| --- | --- | --- |
| s1 | `originals/2026-05-31/31e55ea8a4de42029659654a80814630_src.png` | 1024x1536 |
| s2 | `originals/2026-05-31/37ae95821a3447c78f94e56bdebf0c88_src.png` | 1024x1536 |
| s3 | `originals/2026-07-10/d76f35fee69e4531865e88b786fa52e5_src.png` | 1086x1448 |

All three `detected` before attacks.

## Source-matched pairs (2026-08-21)

`gpt-image-2` (ChatGPT Images 2.0) can mint encoder-on/off pairs.
`chatgpt-image-latest` is 403 until the org is verified.

| Input | C2PA | Oracle | Aligned PSNR |
| --- | --- | --- | ---: |
| Camera JPEG 960x1280 | none | not_detected | - |
| ChatGPT UI + frame 1086x1448 | watermarked.unbound | detected | 16.6 dB (redraw) |
| `gpt-image-1` edit, high fidelity, red dot | created, converted only | not_detected | 30.9 dB |
| `gpt-image-2` edit, red dot 1024x1536 | watermarked.unbound | detected | 28.2 dB |

The `gpt-image-2` photo residual is broadband (std 9.1), not a 16-32 stamp.
COCO `gpt-image-2` edits: 11/12 `watermarked.unbound`, one safety block.

Solid gray/white through `gpt-image-2` "reproduce exactly" is
`watermarked.unbound`. Gray 128 at 1024x1536: PSNR 41.9 dB vs the flat,
source `not_detected`, output `detected`. Other gray levels 32-220: PSNR
38-49 dB. Eight gray 1024x1536 residuals, leave-one-out correlation after
highpass: 0.645 (shuffle 0). That shared stamp does not transfer to COCO
photo residuals (0.007-0.025).

## Presentation gate versus residual

An official `not_detected` is not one event. Collage, photo-pad, two-panel
self-concat, and 8x8 scramble can be a *presentation gate* (this upload is
not a single photograph). Blur sigma 7 and in-band 16-32 destruction sit on
the single-photo manifold and are residual damage; those belong in
[mark removal](synthid-removal-research.md).

Do not train a surrogate on mixed collage misses if the goal is a mark
student.

Identity (s1, 2026-08-19): JPEG q80/q20, crop 2 px, crop 8 px, keep 0.75
and 0.50, rot90, rotate 5, flip, grayscale all stay `detected`.

Token / layout (s1): each quadrant at 512x768 `detected`; `hstack` and
`vstack` of marked\|marked `not_detected`; 4x4 tile scramble `detected`;
8x8 `not_detected`. Two copies of a detecting image still miss. Tomography
3x3: all nine cells `not_detected` (a 1/9 window is below support).

Preprocess E1 (s1): stretch 2x `detected`; centre-crop of marked\|marked
hstack back to native `detected`; 0.20x pixels on a native-size white
canvas `not_detected` (the same 0.20x file uploaded alone was `detected`).

## L1 is not a mark task

Control-only 283 rows: 203 detected, 80 not_detected. Forward-temporal
nested ridge on 124 pixel features: AUC 0.649 / 0.641. Geometry-only:
0.781 / 0.826. All 21 `claim_generator=ChatGPT` controls are
`not_detected`. C2PA `opened`: 24/24 `not_detected`. Inside 1254x1254,
mean-feature permutation p=0.45.

OpenAI-supervised ridge on 16-32 band-passed `image_features`:
forward-temporal AUC 0.53 vs L1 `not_detected`, 0.95 vs COCO, 0.97 vs COCO
after a 2 px crop. The student learns OpenAI-versus-photo and still does
not see the oracle mark contrast.

## Product remainder for the watermark

Signed provenance (`identify`) and `verify-openai-synthid` (remote, explicit
upload). A local `indeterminate` from `detect-synthid` is not a clean
SynthID negative.

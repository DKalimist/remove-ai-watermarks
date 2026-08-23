# Classifier models (research)

> Research archive for pixel classifiers that are *not* SynthID detectors.
> Not a statement of current product capability. Shipped behavior:
> [supported signals](supported-signals.md) and
> [known limitations](known-limitations.md).
>
> Sister pages: [SynthID local detector](synthid-detector-research.md),
> [SynthID mark removal](synthid-removal-research.md),
> [mechanism reference](synthid.md).

A classifier is reliable only when its name matches its errors, photographs
are the first negative, Firefly and PixelBin are in the test, and a watermark
claim uses an independent oracle. CLIP content embeddings and the 124-d
origin-locked residual bank are different features for different jobs.

## Result: Model 1, AI versus camera

Finetuned CLIP-L (`openai/clip-vit-large-patch14`), last two vision blocks,
224 letterbox, JPEG and mild crop, linear ridge. Train 5,221 AI plus 6,129
photos. Locked Open Images fresh never enters train. Operating point: 1%
FPR on disjoint `photo_dev_oi`.

| Cell | Value |
| --- | --- |
| Kodak | 0/24 |
| Open Images fresh FPR | 1.7% (n=3,000) |
| Exact-1024 Open Images FPR | 6% |
| AI-test TPR | 93.0% (n=1,905) |
| OpenAI | 93.2% |
| Gemini | 90.5% |
| Firefly | 94.0% |
| xAI | 96.1% |
| FLUX hold | 92.7% |

51 fresh false positives are mostly graphics, CGI, product cutouts, and
scans, not Gemini. Nobody in the sweep hit both ≤1% fresh FPR and ≥90%
TPR. This is AI-versus-camera, not SynthID, and it is not in `identify`.

Artifacts: `.local-eval/synthid/ai-photo-2026-08-22/`
(`comparison.json`, `probe-report-clip-l-ft.json`,
`probe-weights-clip-l-ft.npz`). Date cutoff 2026-07-23, seed 20260822.

### Rejected Model 1 variants

Same splits and `photo_dev_oi` 1% cut.

| Variant | Fresh FPR | Kodak | 1024 FPR | AI TPR | FLUX hold |
| --- | ---: | ---: | ---: | ---: | ---: |
| CLIP-L v2 | 0.017 | 0/24 | 0.04 | 0.877 | n/a |
| CLIP-L + FLUX extra | 0.016 | 0/24 | 0.05 | 0.861 | 0.707 |
| CLIP-H + FLUX extra | 0.014 | 0/24 | 0.02 | 0.812 | 0.913 |
| CLIP-L last-2-blocks finetune | 0.017 | 0/24 | 0.06 | **0.930** | **0.927** |
| DINOv2-giant 256 | 0.023 | 0/24 | 0.04 | 0.606 | 0.293 |

CLIP-H is the photo-FPR specialist (1.4% fresh, 2% at 1024) at 81% TPR and
is not the result. DINOv2-giant at 256 px is not usable.

v1 (CLIP-L, no Open Images in train) at a COCO-looking 0.5% cut accepted
13% of Open Images. Domain shift, not the 124 residual bank. v2 added
1,000 disjoint Open Images reserve photos to train and 500 as
`photo_dev_oi`; locked fresh stayed 1.7% FPR at 87.7% TPR before
finetune.

The 124-d residual bank is the wrong feature for "AI or not". At a
Kodak-safe cut it catches 60% Firefly and misses FLUX, NovelAI, Reve, and
most of TC260 and xAI. Do not train another ridge on that representation
for an AI-or-not claim.

Open, if this head is ever considered for a product cut: a graphics/CGI
abstain. CLIP treats non-camera imagery as generation; that is the remaining
error, not Gemini contamination.

## Closed: provider names from pixels

Three-way `openai` / `google` / `other` on Model 1 embeddings fails the
Firefly gate. CLIP-L-ft test accuracy 0.53; Firefly 35/31/18. CLIP-H 0.57;
Firefly 36/33/15. OpenAI versus Gemini AUC on CLIP-L-ft is 0.845; on the
124-d lattice bank it is 0.989. They are two pipelines, not one class.

Collapsing OpenAI and Gemini into one pixel class versus other generators
does not fix that. Binary ridge AUC 0.686, TPR 75% at FPR 45%. Canva 98%,
Microsoft 75%, Firefly 68% leak into the union; FLUX HF hold stays out at
3%. Training the same union only against photographs recreates Model 1 with
a narrower train set (fresh FPR 2.1%, Firefly still 95%).

`provider-report-clip-l-ft.json`, `provider-union-report.json`.

### 124-d lattice as pipeline ID, not a vendor CLIP head

Provider-class ridge on 124 native residual features (70/30 once, not a
watermark gate). OpenAI L1 n=285, Google corpus n=533, foreign n=218, COCO
n=289: OpenAI vs COCO 0.965; Google vs COCO 0.999; OpenAI vs Google 0.989;
OpenAI vs foreign 0.725; Google vs foreign 0.922. OpenAI vs Firefly-class
is the weak cell.

One-vs-rest: Google head at TPR 90% has FPR 0% vs COCO, 14% vs foreign, 2%
vs OpenAI. A Gemini-like pixel class is close to what `pipeline_lattice`
already is. An OpenAI-like pixel class on this bank would label Firefly as
OpenAI about half the time and is not shippable.

Three-class `openai` / `google` / `no_ai` on 2,000 catalog OpenAI, 2,000
catalog Google, and 1,936 COCO photos. Photo-first margin 0.50: openai
74.7%, google 78.9%, no_ai 99.8%; Kodak 24/24 `no_ai`. Other generators
are leakage, not classes:

| Platform | n | openai | google | no_ai |
| --- | ---: | ---: | ---: | ---: |
| Firefly | 106 | 37 | 27 | 42 |
| Microsoft | 117 | 39 | 22 | 56 |
| PixelBin | 90 | 14 | 46 | 30 |
| HuggingFace job | 82 | 3 | 62 | 17 |
| ByteDance C2PA | 86 | 5 | 35 | 46 |
| SD / Comfy | 120 | 30 | 11 | 79 |
| fal.ai | 98 | 11 | 18 | 69 |
| Made-with-AI tag | 115 | 4 | 32 | 79 |
| TC260 | 118 | 1 | 13 | 104 |
| xAI | 114 | 1 | 20 | 93 |
| Canva | 76 | 11 | 3 | 62 |
| Apple Clean Up | 114 | 1 | 23 | 90 |
| Aweme | 37 | 2 | 7 | 28 |
| FLUX | 11 | 0 | 0 | 11 |
| Reve | 10 | 0 | 0 | 10 |
| NovelAI | 9 | 0 | 0 | 9 |
| Higgsfield | 11 | 1 | 5 | 5 |

PixelBin and HuggingFace jobs lean `google` (shared renderer lineage).
FLUX, NovelAI, and Reve stay `no_ai`. Local probe:
`uv run python .local-eval/synthid/prc-oklab-attack-2026-08-15/classify_openai_gemini.py image.png`.

## Production `pipeline_lattice` (google-lineage renderer)

Experimental signal in `identify`, never a watermark. Production
`detect_synthid` re-check on 628 frozen holdouts, seed 20260822, threshold
1.0.

| Family | n | detected | rate | max score |
| --- | ---: | ---: | ---: | ---: |
| Google / Gemini | 80 | 45 | 0.56 | 3.03 |
| Firefly | 84 | 15 | 0.18 | 3.00 |
| PixelBin | 80 | 11 | 0.14 | 2.48 |
| Microsoft | 60 | 2 | 0.03 | 2.40 |
| OpenAI | 80 | 1 | 0.01 | 1.38 |
| xAI | 40 | 1 | 0.03 | 1.26 |
| FLUX HF | 40 | 0 | 0 | 0.85 |
| TC260 | 40 | 0 | 0 | 0.97 |
| Kodak | 24 | 0 | 0 | 0.49 |
| Open Images fresh | 60 | 0 | 0 | 0.64 |
| COCO hold | 40 | 0 | 0 | 0.74 |

Firefly 18% and PixelBin 14% match the 2026-08-16 signed-foreign rates
(24% and 14%) in order of magnitude. Both Microsoft hits have issuer
`Microsoft, Google LLC`. A 2 px crop killed every sampled positive,
including Firefly and PixelBin. Google TPR 56% is mixed Spaces eras, not
the oracle-positive 147/148 cell. Honest name:
`google_lineage_renderer` = Gemini/Imagen + Firefly + PixelBin.

Registered-v3 photographic controls remain 0/5,993 Open Images and 0/2,366
COCO. Against 223 C2PA-named non-Google generators on 2026-08-16: 29
accepted (0.130), Firefly 0.241. `.local-eval/synthid/lattice-check-2026-08-22/`.

## Spaces catalog sizes (2026-08-21)

49,082 unique sha256. Unlabeled 24,832 rows are not photographs. Microsoft
127/279 and Firefly 64/210 also carry `synthid_from_provenance=true`, so
that flag is not an OpenAI-plus-Gemini class.

| Platform | n |
| --- | ---: |
| none / unlabeled | 24,832 |
| OpenAI | 11,722 (11,347 SynthID-from-provenance) |
| Google / Gemini | 6,875 (plus 94 Google C2PA without a named generator) |
| China AIGC TC260 (not a brand) | 3,610 |
| Microsoft | 279 |
| Meta-style Made-with-AI tag | 275 |
| Adobe Firefly | 210 |
| xAI | 179 |
| local SD / Comfy | 178 |
| ByteDance platform | 88 |
| fal.ai | 98 |
| Canva | 79 |
| ByteDance Aweme tag | 40 |
| Dreamina tag | 4 |

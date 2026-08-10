# SynthID detector and pixel-only removal research plan

> Research plan, not a statement of current product capability. The shipped
> behavior remains documented in [supported signals](supported-signals.md),
> [known limitations](known-limitations.md), and
> [module internals](module-internals.md).

## Objective

Build two independent provider tracks with four capabilities:

1. a local, metadata-independent detector for the OpenAI SynthID image signal;
2. a local, metadata-independent detector for the Google SynthID image signal;
3. a pixel-only remover for the OpenAI signal that does not use diffusion,
   VAE reconstruction, semantic regeneration, or generative inpainting;
4. an independently calibrated pixel-only remover for the Google signal under
   the same constraints.

OpenAI is the first research track because it has a documented remote verifier.
Google follows with the same experimental protocol but its own corpus, labels,
model, thresholds, and oracle. No carrier, feature, score, or operating point
transfers between providers until a held-out experiment demonstrates that it
does.

The detector target is signal presence, not payload recovery, provider
classification, or general AI-image classification. The removal target is a
minimal pixel residual that makes a source-positive image negative in the
matching provider oracle while preserving the image's geometry and semantics.

## Non-negotiable evidence rules

1. **Detector before remover.** A remover may be prototyped against synthetic
   carriers, but no real-image removal claim is made until the local detector
   passes its own held-out gate.
2. **Provider-specific ground truth.** OpenAI and Google labels come from their
   matching verifier. C2PA is recorded separately and is never the pixel label.
3. **No metadata or export leakage.** Training and evaluation operate on decoded
   pixels after controlled metadata stripping and matched re-encoding. Geometry,
   filename, file size, chunks, encoder settings, and source directories cannot
   be model inputs.
4. **Signal identifiability is a gate.** A classifier trained only on provider
   positives and unrelated negatives can learn the provider's generator or
   export fingerprint. It is called a provider classifier, not a SynthID
   detector, until at least one causal control succeeds.
5. **The oracle is held out from optimization.** Candidate algorithms and
   hyperparameters are selected locally. Oracle batches are immutable and
   registered before submission. A remote binary verdict is never used as an
   online loss or hill-climbing signal.
6. **A local score decrease is not removal evidence.** Removal requires a
   source-positive, output-negative result from the matching provider oracle.
7. **One hypothesis does not become several signals.** Correlated spatial,
   spectral, and color statistics derived from one residual are reported as one
   line of evidence unless independent controls separate them.
8. **Every result is reproducible.** Input and output hashes, code revision,
   model artifact hash, preprocessing, transform lineage, seed, score, threshold,
   quality metrics, oracle result, session, and timestamp are retained.

## Oracle boundary

OpenAI documents a synchronous Content Provenance API at
`POST /v1/content_provenance_checks`. For images it returns separate `c2pa` and
`synthid` entries and supports PNG, JPEG, and WebP. It remains a remote,
OpenAI-scoped verifier, not a released local decoder. The same documentation
explicitly says not to use repeated queries to reverse-engineer, remove, or
evade a watermark. Adaptive detector or remover research against that endpoint
therefore requires explicit OpenAI authorization or a separate research oracle
whose terms permit the work. Without that authorization, the OpenAI track may
develop local hypotheses but stops before oracle-driven calibration and removal
certification.

Google's Gemini verification flow is a Google-scoped oracle. Its documented
result can be detected, not detected, or unclear, and the consumer flow has a
small rolling quota. An unclear result is `indeterminate`, never a negative.

For every permitted oracle batch:

- verify the untouched source first;
- submit one file per request;
- record C2PA and SynthID outcomes independently when both are returned;
- preserve the exact submitted bytes and SHA-256 outside the public repository;
- retry only a transient failure on the same bytes;
- record `detected`, `not_detected`, `indeterminate`, or `refused` verbatim;
- submit a matched transform-only control before attributing a negative result
  to an experimental edit;
- reserve a final temporal holdout that no feature, threshold, or remover has
  seen.

## Data design

### Corpus layers

Each provider gets a separate corpus with five layers:

| Layer | Purpose | Required controls |
| --- | --- | --- |
| Verified positives | Learn and evaluate the real signal | Matching provider oracle, original bytes |
| Same-provider hard negatives | Separate watermark from generator identity | Same surface or model, oracle-negative |
| External hard negatives | Measure false positives | Cameras, scans, edited photos, other generators, synthetic graphics |
| Low-texture probes | Expose weak shared structure | Solid colors, gradients, ramps, checkerboards, sparse edges |
| Causal pairs | Attribute a residual to the watermark | Same underlying pixels, positive and confirmed negative |

The causal-pair layer is the most valuable and the hardest to obtain. An
authorized encoder-off pair is ideal. A provider output and a pixel-only
processed version become a usable pair only after the original is positive and
the processed bytes are negative in the provider oracle. Public third-party
pairs are discovery material until their provenance and both labels are
independently verified.

A negative created by a remover trained against detector A cannot train or
validate detector A in the same experiment. Reserve it for detector B or a later
model epoch after closing the originating experiment. Otherwise detector and
remover can certify each other's shared blind spot.

If no same-provider hard negatives or causal pairs can be obtained, learned
real-image models stay explicitly labeled as provider classifiers. Spectral
repeatability on solid fills alone does not clear this gate.

### Strata

Record and split by:

- provider, product surface, model family, and generation date window;
- native width, height, aspect ratio, file format, and color mode;
- photoreal, face, text-heavy, flat graphic, illustration, low texture, and
  high texture content;
- untouched, metadata-stripped, lossless-normalized, JPEG/WebP, resized,
  cropped, and color-adjusted lineage;
- generation session and prompt family;
- parent hash for every derivative.

Store research media under `.local-eval/synthid/`, not in the public repository.
Only cleared fixtures may enter `data/synthid/`. Tracked files contain schemas,
scripts, synthetic fixtures, aggregate verdicts, and non-sensitive hashes.

### Split discipline

Deduplicate by decoded-pixel hash and perceptual similarity before splitting.
Keep every derivative, prompt sibling, and semantic near-duplicate in one hash
group. Split by group into train, validation, locked test, and a later temporal
test collected after the detector is frozen. A random image-level split is
invalid because it leaks transform and generation-family fingerprints.

The negative set must be large enough to support the claimed operating point.
At zero observed false positives, roughly 3,000 independent negatives are
needed merely to put the one-sided 95% upper bound near 0.1% by the rule of
three. The final evaluation should prefer at least 10,000 hard and ordinary
negatives per provider, report confidence intervals, and report every negative
stratum separately rather than hiding a weak stratum in an aggregate.

## Detector program

### Experiment D0: oracle and corpus integrity

Goal: prove that labels and bytes mean what the manifest says.

- Separate SynthID from C2PA in every response.
- Confirm that metadata stripping changes C2PA but does not silently define the
  SynthID label.
- Confirm every positive used for evaluation on its matching oracle.
- Mutation-test manifest ingestion with swapped provider, duplicate bytes,
  derivative leakage, an `indeterminate` result mislabeled as negative, and a
  changed file after hashing.
- Measure permitted same-byte verifier reproducibility on a small preregistered
  sample. Do not turn retries into adaptive querying.

Gate: no ambiguous label path, no cross-provider oracle substitution, and no
train/test family leakage.

### Experiment D1: export and generator confounds

Goal: determine how accurately SynthID can appear to be detected when no
watermark-specific evidence is available.

Train deliberately confounded baselines on file/container fields, dimensions,
RGB thumbnails, and generator-vs-camera content. Then repeat after canonical
decode, metadata removal, resolution matching, and hard-negative balancing.

Gate: any proposed signal feature must beat the canonicalized confound baseline
on same-provider hard negatives and on a temporal holdout. Otherwise the result
is generator attribution.

### Experiment D2: low-texture carrier discovery

Goal: test whether a repeatable carrier component is observable when scene
texture is suppressed.

Extend the existing `scripts/synthid_pixel_probe.py` measurements from grayscale
NCC to:

- per-channel and opponent-color residuals;
- two-dimensional FFT magnitude and circular phase coherence;
- wavelet bands and multi-scale autocorrelation;
- resolution and aspect-ratio registration;
- cross-color, cross-session, cross-model, and cross-date agreement;
- matched clean synthetic fills and same-provider oracle-negative probes.

Use leave-one-color, leave-one-session, and leave-one-resolution-out tests.
Fixed bins discovered and evaluated on the same images are descriptive only.

Gate: a template learned on one subset must detect held-out positive probes above
matched negatives and survive a later collection window. Failure kills the
fixed-carrier branch but not the content-dependent branch.

### Experiment D3: classical real-image detector

Goal: establish the strongest interpretable baseline before a neural model.

Candidate features include locally normalized high-pass residuals, FFT and
wavelet energy ratios, circular phase coherence, color-channel agreement,
block periodicity, and correlations against provider/resolution templates.
Fit regularized logistic regression and a shallow tree model. Calibration uses
only validation data.

Report TPR at 0.1% FPR as the primary metric, with bootstrap confidence
intervals. AUROC, average precision, and an arbitrary accuracy percentage are
secondary. Also report worst-stratum FPR, temporal-holdout TPR, and score drift.

Gate: advance the classical detector only if the locked test shows a stable
watermark-specific advantage over confound baselines. Do not choose a threshold
from the locked test.

### Experiment D4: learned residual detector

Goal: learn content-dependent evidence that a fixed template misses.

Start with a small two-view model:

1. a spatial view of locally normalized high-pass RGB residuals;
2. a frequency view containing log magnitude and phase-derived channels.

Fuse only late features so each view can be ablated. Use aggressive content and
export balancing, group-aware sampling, and augmentations drawn from the paper's
transformation families. Never expose metadata, path, dimensions without
normalization, or encoder-specific byte patterns to the network.

Train provider-specific models first. A shared backbone with provider-specific
heads is a later ablation, not the default architecture. Keep a second detector
family completely outside remover training so it can reveal surrogate overfit.

Gate for a detector release candidate:

- empirical FPR at or below 0.1% on the locked negative set;
- one-sided 95% TPR lower bound at or above 90% on untouched positives;
- no declared hard-negative stratum above 0.5% FPR;
- useful TPR on the temporal holdout and transformation suite;
- meaningful discrimination on causal pairs or same-provider hard negatives;
- calibrated `abstain` behavior outside supported providers and strata.

These are research gates, not promises that the proprietary decoder's operating
point has been reproduced.

### Experiment D5: robustness and drift

Evaluate identity, JPEG and WebP, resize, crop, padding, rotation, color changes,
blur, noise, overlays, screenshots, and combinations. Preserve a matched
transform-only positive control for every attack family. Report both average
and worst-transform TPR at the frozen threshold.

Repeat a small fixed collection after provider model or surface changes. A
shift in score distribution opens a new model epoch; it does not silently
recalibrate the old threshold.

## Localization program

A whole-image detector is not automatically a useful removal loss. Test whether
its evidence is spatially causal with three independent methods:

- tile occlusion and replacement with distortion-matched controls;
- detector-gradient attribution for the learned model;
- phase or template energy mapped back to spatial blocks.

For each source, create top-ranked, random, and bottom-ranked edits with equal
pixel norm and the same codec path. The oracle batch is registered before any
results return.

Gate: top-ranked edits must reduce matching-oracle detection more often than
random edits under paired analysis. Aggregate per-image differences and confirm
the direction with a sign test. If localization does not transfer, do not build
a region remover around it.

## Pixel-only removal program

All candidates preserve image dimensions and avoid a generative decoder. Run
the following ladder in order.

### Experiment R1: analytical carrier subtraction

Estimate provider, model-epoch, and geometry-specific residual components from
verified probes or causal pairs. Test:

- complex FFT projection with conjugate symmetry;
- wavelet-band projection;
- per-channel and opponent-color residual subtraction;
- spatially varying strength based on local texture and detector attribution.

Sweep signed amplitude, not only attenuation. Include a sham edit with identical
pixel norm outside candidate bins. This is the highest-value path because a real
shared post-hoc residual could be removed at very high fidelity.

### Experiment R2: constrained per-image optimization

Optimize pixels against an ensemble of frozen local detectors. The objective
combines detector margin with L-infinity and L2 bounds, LPIPS or DISTS, MS-SSIM,
edge consistency, OCR preservation, and face-embedding preservation where
applicable. Expectation over transformations covers lossless export, JPEG/WebP,
small resize, and color conversion so the result is not a fragile local
adversarial example.

The optimization may read only local detectors. The provider oracle evaluates
a frozen candidate batch afterward and never supplies gradients, search
direction, or per-step feedback.

### Experiment R3: feed-forward residual remover

If R2 transfers to the provider oracle, distill successful minimal residuals
into a compact image-to-residual network. Constrain the output amplitude and
frequency distribution explicitly. Train on one detector ensemble and select
on the held-out detector family. Preserve the per-image optimizer as the
reference implementation.

### Experiment R4: detector-remover co-evaluation

Evaluate four combinations separately:

1. local detector positive, provider oracle positive;
2. local detector negative, provider oracle positive;
3. local detector positive, provider oracle negative;
4. both negative.

Case 2 is the critical surrogate-overfit failure. Add every permitted example
to a future hard set only after the current experiment is closed; never tune and
report on the same oracle failure.

## Removal success gate

A provider-specific remover is a release candidate only when a locked,
source-positive evaluation shows all of the following:

- at least 90% matching-oracle `not_detected` results, with `indeterminate`
  counted as failure;
- a positive matched transform-only control for every evaluated source;
- exact-size output with no semantic regeneration stage;
- median PSNR at least 40 dB and fifth-percentile PSNR at least 35 dB;
- median SSIM at least 0.99, plus LPIPS or DISTS reported rather than optimized
  silently;
- no OCR regression on text strata and no material face-identity regression on
  face strata under preregistered thresholds;
- no worse oracle-negative rate after a standard downstream JPEG/WebP/resize
  suite;
- byte-identical pass-through for detector-negative inputs by default;
- a significant paired advantage over random and norm-matched sham edits;
- no claim of forensic cleanliness without a separately trained removal-artifact
  detector and a held-out evaluation.

If pixel-only methods fail this gate, retain diffusion regeneration as the
explicit fallback. Do not combine its success with pixel-only results.

## Provider sequence

### OpenAI first

1. Resolve the oracle authorization gate.
2. Build the corpus schema and confound challenge.
3. Verify or reject the shared-carrier hypothesis on low-texture probes.
4. Train classical and learned detectors.
5. Freeze the detector and temporal test.
6. Run R1, then R2, then R3 only after each preceding gate passes.
7. Submit one preregistered final oracle batch.

OpenAI work establishes the experimental machinery, not parameters for Google.

### Google second

Repeat the full sequence with Google-native positives, Google hard negatives,
and the Gemini oracle. Spend the small manual oracle budget on controls and
decisive boundary points, not uniform sweeps. Use local detector uncertainty to
choose a batch before submission, then freeze it. Test Gemini app and AI Studio
surfaces as separate strata because their export and metadata paths differ.

## Implementation order

The research harness remains outside the public API until the gates pass.

1. **Implemented:** use the private corpus schema and auditor documented in
   [`data/synthid/research-manifest.md`](../data/synthid/research-manifest.md) to
   record provider, surface, model epoch, session, content stratum, parent hash,
   transform lineage, separate C2PA and SynthID outcomes, oracle session, and
   artifact hashes.
2. **Implemented:** build a label-free local inventory before promotion so byte-identical files,
   decoded-pixel duplicates, and unsupported formats are visible without
   inferring evidence from directory names.
3. **Implemented:** add a corpus auditor that rejects hash-group leakage, missing parent links,
   ambiguous labels, and unsupported oracle-provider pairs.
4. **Harness implemented; evidence run pending:** run the manifest-driven D1
   challenge over container, thumbnail, and canonical decoded-content
   baselines. Freeze its validation threshold and report same-provider negative
   cohorts separately.
5. Generalize `scripts/synthid_pixel_probe.py` into reusable feature extraction
   while preserving its current synthetic tests.
6. Add reproducible train/evaluate commands whose output is a versioned model
   card and metrics snapshot, never an unversioned console claim.
7. Add analytical and optimization removal harnesses with norm-matched controls.
8. Reuse the existing fidelity scripts for PSNR, SSIM, OCR, face, and edge
   measurements, adding only missing metrics.
9. Package provider-specific detector weights behind an optional dependency only
   after the detector gate passes.
10. Add a runtime remover and CLI surface only after the removal gate passes.

Pure feature, manifest, split, threshold, and residual-constraint logic must be
unit-tested without model downloads. Real model and oracle runs stay explicit
research jobs.

The inventory, manifest auditor, and D1 confound harness now exist as local
research tools. D1 has not produced a real-corpus metric yet because existing
artifacts have not been promoted into evidence-bearing provider manifests. This
is an evidence gap, not permission to infer labels from their paths. The next
real D1 run begins only after ordinary rows cover train, validation, locked test,
same-provider hard negatives, and a two-class temporal holdout.

## Empirical log

### 2026-08-09: fixed spectral-template baseline rejected

An exploratory Google template was reconstructed from four public, purported
clean/marked pairs. Their provenance and oracle status could not be established,
so they were used for discovery only. A scalar phase-consensus score and its
threshold were selected on those pairs, four older Google-oracle positives, and
30 external negatives.

The frozen threshold then produced six false positives on a new 100-image
external holdout. It also detected only one of four newly generated Gemini
images collected after threshold selection. Duplicate-image removal cannot
reduce the false-positive rate enough to approach the 0.1% detector gate, and
the temporal result is far below the required sensitivity. The baseline is
therefore rejected, not recalibrated on the holdout.

This result rules out the fixed phase template as a detector or removal loss.
It does not rule out a content-adaptive or model-epoch-specific signal. The
next detector must learn from independently labeled provider data, must retain
the failed holdout unchanged, and must demonstrate discrimination from export
format and generator identity.

### 2026-08-09: cross-color low-texture consensus rejected

A polarity-invariant consensus template was trained on black, white, and red
Gemini low-texture probes and frozen before evaluation. Its median score fell
from 0.574 on the training groups to 0.354 on held-out probes of the same
colors and 0.011 on unseen blue, green, and gray probes. External negatives had
a median score of 0.0047. The separation therefore depended on the training
colors and did not generalize across the intended low-texture stratum.

This branch is rejected as a current Google detector. It remains useful as a
negative control demonstrating why high training coherence is not evidence of
a shared carrier.

### 2026-08-09: external V3 codebook detector pilot

The numeric format-v2 V3 artifact from `reverse-SynthID` was loaded with pickle
disabled and evaluated independently; no third-party code was imported or
executed. A 256-bin phase score with a discovery-frozen threshold of 0.5
detected five of five Google-oracle-positive images and produced zero false
positives on 194 external images collected before and after threshold freeze.
The pilot includes four older positives and one newly generated temporal
positive. It is promising discovery evidence, not a released detector:

- zero errors on 194 negatives cannot support a 0.1% FPR claim;
- the set lacks enough same-provider, oracle-negative hard controls;
- the phase profile is a third-party artifact whose positive provenance is not
  independently reproducible from our current corpus;
- a secondary `active_weight_fraction` shortcut failed on an exact-resolution
  holdout, firing on 17 of 50 new negatives, and is rejected as a
  native-resolution/content confound.

The next detector milestone is to reproduce the phase carrier from our own
deduplicated positives, expand the negative set to at least the rule-of-three
minimum, and add same-provider hard negatives before fitting or publishing an
operating point.

### 2026-08-09: independently fitted phase-carrier pilot

An exact-geometry phase model was then fitted from four of our own
Google-oracle-positive images. The first unconstrained search was a clear
multiple-comparisons failure: training scores were 0.983-0.991, while the
newly confirmed fern positive scored 0.061 and an exact-resolution negative
reached 0.105. Leave-one-out discovery detected only two of four older
positives. That unrestricted model is rejected.

A second model used only the 256 frequency coordinates proposed by the numeric
V3 artifact, while relearning phase, weight, and expected magnitude entirely
from our four positives. This restricted model scored the fern validation
positive at 0.740 and the four fitting positives at 0.936-0.963. A threshold of
0.43 was frozen after 50 validation negatives whose maximum was 0.305.

The phase-only epoch failed its first new holdout with three false positives in
121 exact-size images. All three had active carrier weight between 0.07 and
0.14, so the failed epoch was closed and a new rule was frozen: phase score at
least 0.43 and active weight at least 0.50. That second epoch produced zero
false positives on 279 newly downloaded exact-size images.

A separate 3,000-image COCO check also produced zero joint-rule positives, but
it is not counted toward the supported-stratum FPR bound. Every COCO image had
been upscaled to the model geometry and every active weight was at most 0.201.
The rule therefore abstained because the inputs were outside its measured
carrier-support distribution. Treat active weight as an `abstain` gate, not as
negative SynthID evidence.

This is the first positive local-detector pilot derived from our labels, but it
does not clear the detector gate. It still depends on third-party candidate
coordinates, has only five confirmed positives including the fitting images,
has only 279 fresh negatives inside the current support stratum, and has no
same-provider hard negatives. The next epoch requires a larger independently
labeled positive set, at least 3,000 native-support negatives, same-provider
oracle negatives, and a new temporal positive that has not influenced feature
or threshold selection.

### 2026-08-09: color-space spectral comparison

The restricted phase-carrier experiment was repeated in RGB, full-range
YCbCr, YCoCg, an orthogonal opponent basis, CIE Lab, and HSV. Every branch
started from the same 102 spatial frequencies: the top 256 external codebook
coordinates contained 102 unique `(row, column)` pairs, which were expanded
over all three components. Each branch then independently selected 256 of the
306 component-frequency candidates and relearned phase, expected magnitude,
and weight from the same four oracle-positive fitting images. The score was
the phase score multiplied by active carrier weight, so weak spectral support
reduced rather than merely qualified the evidence.

Thresholds were frozen from the fern validation positive and 50 exact-size
validation negatives before scoring the 279-image comparison set. The
comparison set was locked for this color-space branch, although it had already
served as the second epoch's RGB negative set and is therefore not a globally
virgin corpus.

| Space | Validation gap | Comparison negative max | Fern minus negative max | False positives |
|---|---:|---:|---:|---:|
| RGB | 0.509 | 0.097 | 0.459 | 0/279 |
| YCbCr | 0.330 | 0.193 | 0.312 | 0/279 |
| YCoCg | 0.437 | 0.163 | 0.390 | 0/279 |
| Opponent | 0.351 | 0.167 | 0.339 | 0/279 |
| Lab | 0.408 | 0.126 | 0.382 | 0/279 |
| HSV | 0.530 | 0.084 | 0.495 | 0/279 |

HSV had the best observed worst-negative margin, narrowly ahead of RGB, but
did not generally shift paired negatives below RGB. After normalizing each
space by its fern score, the median paired HSV-minus-RGB difference was 0.0015
and a two-sided sign test gave `p=0.632` (144 higher, 135 lower). The result is
therefore a tail observation, not evidence that HSV dominates RGB.

Channel decomposition localized the useful effect. HSV hue contributed only
0.012 of fern evidence and its fern-minus-holdout-maximum channel gap was
-0.024; saturation and value contributed 0.333 and 0.233, with positive gaps
of 0.273 and 0.194. In YCbCr, YCoCg, opponent, and Lab, the luminance-like
channel supplied the largest and most stable separation, while chroma-channel
gaps were much smaller. This supports a carrier expressed across intensity and
contrast structure, with useful nonlinear saturation/value projections, not a
hue-specific watermark.

This experiment does not raise the detector's evidence grade. It still has
only one held-out confirmed positive, reuses the same third-party spatial
frequency prior, lacks same-provider hard negatives, and evaluates only one
native geometry. A future HSV S+V ablation must freeze its own operating point
and use a new negative epoch and new oracle-positive images; dropping hue now
would be a post-holdout model choice.

### 2026-08-09: pixel-only R1 pilot did not transfer

Three non-generative candidate families were frozen locally before Gemini
verification:

1. local visible-region inpainting changed 0.087% of pixels at 47.64 dB PSNR
   and 0.99963 SSIM;
2. sparse complex-spectrum subtraction used 256, 4,096, or 16,384 numeric V3
   bins while preserving native 2816x1536 geometry;
3. deterministic spatial fragmentation combined smooth local warps, one global
   resampling operation, mild color changes, and codec round-trips.

Local inpainting left the 256-bin phase score effectively unchanged. Healthy
Gemini sessions continued to detect both the target and its spatially shifted
sham, refuting an earlier one-off `not detected` response.

The widest spectral candidate reduced the frozen 256-bin phase score from
0.639 to 0.124 while retaining 51.94 dB PSNR and 0.99854 SSIM. A
pixel-identical, metadata-normalized source control was detected in two healthy
oracle sessions. The 16,384-bin candidate remained detected in one of them and
the second hit quota before returning a verdict. The 4,096-bin candidates also
remained detected. Therefore the external phase carrier is correlated with the
Google signal but is not a sufficient removal loss.

One additional profile returned `not detected` for the 16,384-bin candidate,
then also returned `not detected` for the untouched source. That entire session
is invalidated rather than counted as removal success. This failure adds a new
oracle-health rule: every account/session batch starts with the same
pixel-identical positive control; candidate verdicts are discarded when that
control is not positive. Quota and tool-unavailable responses remain
`indeterminate`.

The frozen fragmentation batch is not yet oracle-resolved because healthy
profiles exhausted their rolling quota. Its balanced and strong variants also
fall below the release fidelity gate locally, so even a future negative oracle
result would be a mechanism-discovery result, not a releasable remover.

A follow-up bounded-warp batch replaced RMS-normalized displacement with strict
per-axis maxima of 1.0, 1.8, and 2.8 pixels. The 1.0-pixel variant retained
37.79 dB PSNR and 0.9784 SSIM but left the local phase score essentially
unchanged at 0.643. The 2.8-pixel variant reduced the score only to 0.503 while
falling to 28.21 dB and 0.8570 SSIM. A multi-transform bounded variant reached
0.159 locally only at 21.97 dB and 0.6749 SSIM. Spatial fragmentation therefore
does not approach the release fidelity gate in this implementation and remains
a preregistered mechanism probe for the next healthy oracle window, not a
product candidate.

### 2026-08-09: positive-only RGB plus S/V detector epoch

The color-space result was converted into a deliberately one-sided research
detector. It requires exact 2816x1536 geometry, RGB evidence of at least 0.302,
HSV saturation-plus-value evidence of at least 0.302, and active carrier
support of at least 0.50 in both branches. It emits `positive` only when every
condition passes and emits `abstain` otherwise; it never claims that SynthID is
absent.

Leave-one-positive-out fitting passed all four older Google positives. Their
minimum held-out RGB evidence was 0.527, minimum held-out S+V evidence was
0.452, and minimum active support was 0.600. The final frozen models detected
all five available oracle-positive controls. A new Picsum epoch downloaded
IDs 600-999; after exact-geometry validation and content-hash deduplication
against all earlier epochs, 330 images remained. None produced a positive
verdict. However, 328 of 330 abstained for insufficient carrier support and
only two reached both support gates before falling below the evidence
thresholds. This validates a positive-only signal catcher inside one geometry,
not a two-sided detector or a general FPR claim.

### 2026-08-09: ensemble phase projection is not a sufficient removal loss

An analytical pixel-only attack removed the positive complex projection onto
the learned RGB phases and HSV S/V phases. One iteration at strength 0.5
cleared the local ensemble at 56.03 dB PSNR, 0.99909 SSIM, and a maximum pixel
change of two levels. A norm-matched random-noise control remained locally
positive.

The provider result rejected this loss as sufficient. In a Gemini session
where the untouched fern control returned `SynthID Status: Detected`, all
three preregistered projection candidates at strengths 0.5, 0.75, and 1.0 also
returned detected. The strongest candidate had negative local RGB and S+V
evidence at 51.97 dB PSNR. The ensemble therefore tracks a real correlate but
does not cover all evidence used by Google's decoder.

### 2026-08-09: 16x32 periodic-tile carrier hypothesis

The failed global projection exposed a more specific spatial structure. Of
the top 256 external V3 bins at 1536x2816, 208 (81.25%) lie exactly on an FFT
lattice spaced by 96 rows and 88 columns. This corresponds to a spatial cell
of `1536 / 96 = 16` rows by `2816 / 88 = 32` columns. Instead of subtracting a
small list of harmonics, a new pixel-only probe high-pass filters the image,
folds the residual modulo 16x32 over 8,448 repeats, and subtracts the complete
zero-mean folded template.

On the fern positive with its visible sparkle already removed, the mildest
locally clearing candidate used Gaussian sigma 0.6 and strength 1.5. The
phase-aligned template cleared the ensemble at 57.03 dB PSNR and 0.99911 SSIM;
the same template shifted by one row and one column remained positive at
57.02 dB and 0.99912 SSIM. Two additional aligned/shifted pairs reproduced the
direction at 55.96 and 54.19 dB.

The per-image estimator was then run on the four older positives with a frozen
strength ladder. The minimum locally clearing strength was 2.0 for three
images and 1.5 for one. All four phase-aligned outputs abstained, while all
four same-strength one-pixel-shifted controls remained positive. Selected
outputs retained at least 55.67 dB PSNR and 0.99874 SSIM. This is the strongest
local causal evidence so far because effect direction follows exact tile
phase at matched distortion across five contents.

It is not a removal result. In a healthy Google verifier session, the fern
source control was detected and the mild aligned sigma-0.6, strength-1.5
candidate was also detected. The stronger local variants therefore remain
unresolved rather than inheriting a negative label from the local ensemble.
Cross-resolution tile discovery and same-provider hard negatives also remain
open.

### 2026-08-09: provider-specific phase losses failed both remote verifiers

The Google result above and a separate OpenAI experiment closed the first
analytical-loss epoch. The OpenAI branch fitted an 8-pixel phase pattern from
OpenAI low-texture outputs and produced a 46.70 dB candidate whose local phase
score changed sign. A single frozen submission to OpenAI Verify still returned
`SynthID detected`; C2PA was absent because the candidate had been re-encoded.
This confirms that metadata removal and a local phase-score reversal do not
establish pixel-watermark removal.

The experiments are not cross-provider replications. Google images were sent
only to Google Verify AI and the OpenAI candidate only to OpenAI Verify. No
carrier, threshold, response, or verdict was transferred between tracks.
OpenAI's published verifier guidance prohibits repeated queries for watermark
reverse engineering or evasion, so that one failed query did not start an
adaptive loop. Further OpenAI candidates remain local hypotheses unless an
authorized research oracle becomes available.

### 2026-08-09: JPEG-robust periodic EOT surrogate pilot

Small residual CNNs were trained separately for each provider as differentiable
attack surfaces. They are provider classifiers, not SynthID detectors: their
corpora lack current same-provider oracle-negative controls, and several
external negatives approach the positive range. Two same-architecture models
were used for optimization and a third model with a different first kernel and
channel schedule was kept outside the attack.

For Google, all three models scored the temporal fern positive at a 75th-patch
percentile between 0.938 and 0.962. A patch-local L-infinity-8 attack initially
cleared the models and survived JPEG, but visual inspection exposed rectangular
grid boundaries; that candidate was rejected despite favorable scalar metrics.
A replacement optimized one 16x32 residual cell repeated over the full image,
with differentiable JPEG-95 and JPEG-90 branches. At half strength it retained
36.80 dB PSNR and 0.9241 SSIM against the icon-clean source. The three PNG
scores fell to 0.024, 0.047, and 0.016; after an actual JPEG-90 round trip they
were 0.182, 0.243, and 0.016. The independent RGB and HSV S+V phase ensemble
also abstained, and remained below threshold after JPEG-90, JPEG-95, WebP-95,
and a 0.98 resize round trip.

For OpenAI, the held-out complex market image scored 0.936, 0.929, and 0.813
on its three provider classifiers. An independently optimized 8x8 periodic EOT
residual was then attenuated in low-texture regions. The selected local
candidate retained 34.97 dB PSNR and 0.9356 SSIM. Its PNG scores were 0.030,
0.053, and 0.099; after actual JPEG-90 they were 0.042, 0.063, and 0.178.
WebP-95 behaved similarly, while a 0.98 resize raised the independent model to
0.692 and remains a measured weakness. A second optimization that included a
resize branch improved the two optimized models but transferred worse to the
independent model, so it was rejected.

The periodic residuals were then tested for cross-image transfer without
further optimization. The OpenAI 8x8 cell learned from the market image was
applied with the same low-texture attenuation to 11 other OpenAI positives.
Every image moved downward on all three models, both as PNG and after an actual
JPEG-90 round trip. Median PNG scores changed from 0.971, 0.970, and 0.931 to
0.016, 0.033, and 0.036. Each model had 11 of 11 paired decreases, giving a
two-sided exact sign-test `p=0.00098`; per-image PSNR ranged from 33.50 to
35.99 dB. Two complex scenes retained materially higher scores on the
independent model, so the transfer is strong but not uniform.

The Google 16x32 EOT cell was likewise applied to the four older images after
their own locally clearing phase-tile subtraction. All four remained phase
ensemble abstentions, and every CNN score decreased in the lossless outputs.
JPEG-90 preserved the direction but restored the two optimized models to
roughly 0.58-0.78 on the hardest images. Fidelity was approximately 37.25 dB
PSNR. With only four paired images this is descriptive transfer evidence, not a
statistical or oracle gate.

These are positive local robustness results, not watermark-removal results.
Neither candidate meets the release fidelity gate, neither CNN ensemble has
cleared the detector-identifiability gate, and neither selected EOT candidate
has a matching-provider negative oracle verdict. A three-file Google batch is
hash-frozen outside the repository for the next healthy quota window: the
positive source, the stronger phase-only ablation, and the combined periodic
EOT candidate. Results will be accepted only in that fixed order without
between-query adaptation. The first later attempt detected the positive source,
then returned a usage-limit response for the phase-only ablation; that response
is `indeterminate`, and the combined candidate was not submitted out of order.
The OpenAI candidate is not scheduled for the public verifier under the current
usage restriction.

### 2026-08-09: OpenAI fidelity and architecture-transfer frontier

Further local experiments tested whether the OpenAI periodic result could move
above the release fidelity gate without losing transport robustness. Chroma-only
projection reached 47.43 dB PSNR, but an actual JPEG round trip removed the
perturbation and restored the two classifier scores to approximately 0.9. Mixed
luminance/chroma projections and stronger texture masks did not improve that
frontier. A regularized Adam attack reached 41.21 dB on the source image, but
JPEG-90 restored the optimized classifiers to 0.90 and 0.91, and the independent
architecture scored 0.89. This rejected post-hoc color projection and simple
regularization as fidelity remedies.

A second experiment put actual OpenCV JPEG and WebP results in the forward pass
and used a straight-through gradient. At 40.08 dB, actual JPEG-90 still scored
0.89 and 0.91 on the optimized models. Removing the luminance penalty improved
the first model to 0.76 but left the second at 0.88 and reduced fidelity to
38.78 dB. The exact-codec forward pass therefore corrected an invalid transport
approximation, but did not produce a new Pareto candidate.

An architecture-diverse fourth classifier used fine RGB residuals, broader RGB
residuals, and luminance/opponent-color residuals. The market image remained
outside its training split. Its 75th-patch percentile ranged from 0.983 to 0.988
on four held-out OpenAI positives; the median across 120 held-out COCO negatives
was 0.041 and the maximum was 0.521. This is useful attack-surface diversity, not
a certified detector, because no current same-provider oracle-negative corpus is
available.

Adding that model to periodic optimization did not improve architecture transfer.
The preregistered local winner retained 34.86 dB and scored 0.057, 0.197, and
0.021 after JPEG-90 on the three optimized models, but the independent model
scored 0.573. A per-image half-resolution perturbation produced a higher-fidelity
41.86 dB candidate; JPEG-90 scores on its optimized models were 0.587, 0.572,
and 0.471, while the independent model remained at 0.875. Optimizing only the
two original models produced the same failure on both independent architectures.

The measured local frontier is therefore unchanged. The 34.97 dB periodic
candidate remains the strongest transport-robust and cross-architecture result;
the candidates above 40 dB are architecture-specific and cannot support a
removal claim. No additional public OpenAI verifier requests were made during
these experiments.

## Decision record

The program has four possible honest outcomes per provider:

| Outcome | Product consequence |
| --- | --- |
| Causal signal and detector both generalize | Continue to pixel-only removal |
| Detector works but causal attribution fails | Ship no SynthID detector claim; retain as provenance research |
| Detector generalizes but pixel-only removal does not transfer | Keep local detection, retain regeneration fallback |
| Pixel-only removal clears the oracle with quality gates | Productize provider-specific detector and remover |

Stopping at a failed gate is a result. It prevents a local surrogate, export
fingerprint, or quality metric from being mistaken for control over SynthID.

## Immediate first milestone

The first milestone produces no shipping code. Harness code already exists for
items 1 and 5; milestone delivery means a completed evidence-bearing artifact,
not merely an available script. It delivers:

1. the private-corpus schema and auditor;
2. an OpenAI authorization decision for use of the remote provenance verifier;
3. an independently verified status for candidate causal pairs;
4. a canonicalized OpenAI pilot set with hard negatives;
5. the D1 confound report;
6. the D2 low-texture carrier report with leave-one-group-out results;
7. a go or no-go decision for real-image detector training.

Only after this milestone should implementation of D3 and D4 begin.

## Primary sources

- OpenAI, [Content provenance](https://developers.openai.com/api/docs/guides/content-provenance).
- Google, [Verify AI-generated images, videos, and audio](https://support.google.com/gemini/answer/16722517?hl=en).
- Gowal et al., [SynthID-Image: Image watermarking at internet scale](https://arxiv.org/abs/2510.09263).

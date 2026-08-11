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

### Mechanism hypotheses for D3-D5

The next detector epoch tests these hypotheses as one preregistered program:

1. **Counterfactual labels.** Train and calibrate on source-matched
   clean/watermarked examples, ideally the same underlying image before and
   after encoding. A result that vanishes when source, date, codec, and
   dimensions are balanced is a provider fingerprint, not watermark evidence.
2. **Canonical full-field evidence.** Preserve a 512x512 image-level field,
   absolute residual amplitude, and chroma alongside normalized residuals.
   Compare it against the frozen patch baseline on source-disjoint pairs.
   Failure to improve paired low-FPR detection rejects the added global context.
3. **Registration.** Score several bicubic canonical views spanning small scale,
   crop, and offset changes, then aggregate before calibration. This tests
   whether synchronization is distributed across the image rather than fixed to
   one global phase or local grid.
4. **Independent detection head.** Learn one presence logit directly. Treat
   payload-like or phase-consistency heads as auxiliary evidence, not as the
   presence decision. Their inclusion must improve a held-out paired test, not
   only attack-surface scores.
5. **Symmetric transformation channel.** Apply the identical sampled codec,
   resize, crop, color, noise, or overlay operation to both members of a pair. A
   transform is admitted only when the reference decoder, where available,
   confirms that the transformed positive remains valid.
6. **Encoder versions.** Compare one universal model with version- or
   epoch-specific experts on a cross-version transfer matrix. A version split is
   useful only if it improves held-out likelihood without source metadata at
   inference.
7. **Content-dependent watermarkability.** Measure flat, low-contrast,
   monochrome, logo, and pixel-art strata separately. Allow a
   content-conditioned expert or abstention instead of forcing one global
   operating point.
8. **Two-sided calibration.** Calibrate empirical evidence for both `not
   watermarked` and `watermarked`, returning positive, negative, or abstain.
   External generator corpora enter afterward as an untouched false-positive
   challenge, not as a substitute for counterfactual negatives.

### Experiment D4: learned residual detector

Goal: learn watermark presence from counterfactual image-level evidence that a
fixed template misses.

The primary model uses a full canonical field with raw RGB or luminance/chroma,
absolute-amplitude fine and coarse residuals, and optional stationary-wavelet
and complex-frequency branches. Every optional representation is encoded
separately and fused late; early channel concatenation is not a valid ablation.
Locally normalized patch evidence remains a frozen baseline, not the primary
input. Multi-view registration is aggregated into one image-level presence
logit. Payload-like, phase, localization, and content-watermarkability heads are
auxiliary and must prove an incremental held-out benefit.

Use group-aware pair sampling and apply every sampled transformation
symmetrically to the clean and watermarked members. Never expose metadata,
paths, native dimensions without normalization, or encoder-specific byte
patterns to the network. If causal pairs remain unavailable, do not advance a
learned model from provider classification to this experiment.

Train provider-specific models first. A shared backbone with provider-specific
heads is a later ablation, not the default architecture. Keep a second detector
family completely outside remover training so it can reveal surrogate overfit.
Compare a universal head with version-specific experts, and calibrate the
selected model with two-sided empirical evidence so ambiguous inputs abstain.

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

### 2026-08-09: D1 confound pilot and codec challenge

The manifest-driven D1 harness was run on the frozen Google pilot containing
five oracle-positive images and 330 deduplicated exact-geometry external
photographs. The manifest passed byte, decoded-pixel, lineage, and split
verification. It is not evidence-ready because the locked test contains no
same-provider hard negative.

The container-only baseline separated the labels perfectly because the pilot
still exposes format and export-geometry differences. That result is a measured
confound, not watermark evidence. The canonical 8x8 decoded-content baseline
was much weaker: locked-test AUC was 0.620 and temporal AUC was 0.533, and its
validation-frozen threshold detected neither held-out positive. The existing
positive-only RGB plus HSV S/V ensemble still detected all five positives and
emitted no positive verdict on the 330 frozen external images.

A codec challenge re-encoded every positive without changing geometry. The
ensemble remained positive on five of five JPEG-95 outputs and five of five
WebP-95 outputs; JPEG-90 retained three of five. This rejects a bare PNG versus
JPEG container explanation, but does not exclude a generator or source-pipeline
correlate. With only five positives, the one-sided 95% lower bound on TPR is
54.9%. With zero positives among 330 external images, the one-sided 95% upper
bound on FPR is 0.904%, still nine times the 0.1% detector target. Four positives
also participated in model fitting, leaving only one independent temporal
positive. The next valid detector claim still requires new oracle-positive
images and ordinary same-provider oracle-negative controls.

A post-freeze source-provenance challenge then added three exact-geometry
Google originals that had not influenced fitting or threshold selection. Each
carried the same signed Google LLC C2PA issuer, trained-algorithmic-media source
type, and explicit SynthID-present assertion as the detected temporal control.
The ensemble abstained on all three: two lacked active carrier support in both
branches, and the third passed RGB evidence but missed the HSV S/V evidence and
support gates. These are provider-signed embedding assertions rather than
matching-oracle pixel labels, but zero positives in three new same-geometry
images falsifies the current ensemble as a general Google SynthID detector. The
measured phase family is retained only as an epoch- or surface-specific
correlate pending a broader oracle-labeled corpus.

A follow-up cross-epoch check found that the correlate is not entirely confined
to the original five images. RGB and HSV models fitted only on the three later
images ranked each of the five earlier images above all 329 external negatives
in both color spaces (AUC 1.0), but thresholds derived from the later fitting
scores transferred poorly: the strict RGB-plus-HSV decision retained only one
of five earlier positives at zero false positives on the 279-image holdout. An
eight-fold leave-one-positive-out refit across both source groups then detected
six of eight excluded positives with the same RGB-plus-HSV conjunction and each
branch frozen just above its 50-image calibration maximum. RGB alone put all
eight excluded positives above that maximum, while HSV missed the geometric and
low-texture images; the per-fold RGB operating points also produced between one
and eight false positives on 279 held-out negatives.
This is evidence for a transferable but content- and epoch-sensitive Google
pixel correlate, not a shippable detector. The experiment still lacks ordinary
same-provider oracle negatives, and its external-negative set is too small for
the 0.1% false-positive target.

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
between-query adaptation. Two later attempts detected the positive source, then
returned a usage-limit response for the phase-only ablation. In the latest
attempt the verifier requested a retry after 17 hours. Both responses are
`indeterminate`, and the combined candidate was not submitted out of order. The
OpenAI candidate is not scheduled for the public verifier under the current
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

### 2026-08-09: mechanism reset and paired open-method control

The first detector epochs optimized the wrong statistical problem. The
[technical reference](synthid.md#11-post-hoc-model-independent-design) now
records the paper's paired training target, symmetric transformation channel,
independent detection logit, and two-sided calibration. Applied to the initial
pilots, those details reject three implicit assumptions: that a carrier phase
can stand in for the detection score, that mean patch classification is an
adequate image-level decoder, and that a sigmoid threshold calibrated on
unrelated negatives is a deployable decision rule.

A bounded open-method control tested the architecture concern without claiming
that another watermark reproduces SynthID. TrustMark P was used only because
its public encoder creates causal clean/watermarked pairs and its public decoder
can validate transformed labels. Ninety public COCO images were split by source
image into 60 training, 15 calibration, and 15 test pairs. Each pair received
the same identity, JPEG-90, 0.8 resize round trip, or 5% crop transformation.
The official decoder detected 14/15, 15/15, 14/15, and 15/15 transformed marked
test images respectively, with zero detections on the corresponding clean
images.

The existing normalized residual patch recipe reached only 0.707 identity AUC
and 0.668 aggregate AUC on the held-out pairs. A small full-field model that
retained RGB amplitude plus fine and coarse residuals reached 0.947 identity AUC
and 0.841 aggregate AUC. At a threshold above every calibration negative, their
aggregate TPRs were 5% and 20% respectively. Both models failed to reproduce
the official decoder's JPEG robustness. This small proxy is not a TrustMark
benchmark and says nothing directly about SynthID accuracy. It does falsify the
claim that the current patch-normalized architecture and training recipe are an
adequate generic neural-watermark detector.

The resulting eight falsifiable hypotheses now define the canonical
[D3-D5 mechanism program](#mechanism-hypotheses-for-d3-d5). In particular,
external generator corpora remain a final false-positive challenge and do not
substitute for counterfactual negatives.

Until the counterfactual-label and full-field gates pass, the current residual
CNN remains a useful vendor-triage stage for a future cascade, but it is not a
SynthID detector and should not be optimized as the final decision surface.

### 2026-08-09: paired wavelet and spectral ablation

The paired spectral harness was extended with three-level undecimated `db2`
wavelets, complex Fourier phase coherence and power, cepstral peaks, and a
cyclic clean/marked permutation control. The implementation streams wavelet and
spectrum field accumulators rather than stacking transformed fields across
pairs.

On 60 public TrustMark P training pairs at canonical size 256, the true
residuals had mean inter-pair RGB NCC of 0.097-0.121. Cyclically mismatching each
clean image with the next marked image reduced all three channels to about
-0.017. The strongest coherent Fourier cluster occurred around vertical offsets
9-11 and was strongest in the blue channel. Wavelet repeatability was greatest
in horizontal detail bands at levels 1 and 2. These are causal residual
measurements for the open proxy, not evidence about SynthID's carrier.

The representations then faced a source-disjoint single-image test with 60
training, 15 calibration, and 15 test pairs under identity, JPEG-90, 0.8 resize,
and 5% crop transformations. A fixed spectral-template score reached only 0.618
identity AUC and collapsed to 0.498 under crop. A 318-feature wavelet/spectral
summary reached 0.653 aggregate AUC and zero TPR at the threshold above every
calibration negative.

Full-field neural ablations at size 128 gave the following aggregate results:

| Input | AUC | Paired wins | Test FPR | Test TPR |
| --- | ---: | ---: | ---: | ---: |
| Spatial RGB plus residuals | 0.723 | 57/60 | 0% | 11.7% |
| SWT maps only | 0.671 | 59/60 | 0% | 0% |
| Complex FFT maps only | 0.516 | 41/60 | 0% | 0% |
| Spatial plus SWT, late fusion | 0.665 | 59/60 | 5.0% | 8.3% |
| Spatial plus SWT plus FFT, early fusion | 0.639 | 57/60 | 1.7% | 1.7% |
| Spatial plus SWT plus FFT, late fusion | 0.698 | 54/60 | 0% | 0% |

The table uses one threshold above every calibration negative; test FPR is
reported separately because a clean calibration result does not guarantee a
clean locked test.

The SWT branch contains weak, unusually consistent paired evidence, but it did
not improve the spatial model's source-disjoint discrimination in this small
proxy. The FFT map branch was indistinguishable from chance. Therefore neither
representation advances into the primary detector by default. SWT remains a
late-fusion ablation for a larger paired corpus; complex spectral analysis
remains a residual-discovery diagnostic unless a future held-out test reverses
this result.

### 2026-08-09: closed-corpus architecture and score ablations

A temporally split closed three-class corpus then tested whether the open-proxy
architecture result transferred to real external-source images. These labels
establish source classes, not watermark presence; they can measure
generalization and false positives but cannot substitute for counterfactual
clean/marked labels.

The frozen normalized-patch baseline was repeated over three training seeds.
Individual original-image AUCs ranged from 0.864 to 0.879. Averaging the three
models increased AUC to 0.884, but a threshold above every validation negative
still produced one false positive among 259 test negatives. At that operating
point the two positive-source TPRs were only 2.45% and 8.97%. Calibrating near
1% validation FPR yielded 1.54% test FPR and TPRs of 6.68% and 18.16%.
Accepted positives had 98.8-100% vendor accuracy, so vendor attribution is
useful only after an independently reliable presence decision.

A naive full-field spatial model reached only 0.599 AUC. Adding a separately
encoded stationary-wavelet branch and late fusion reduced AUC to 0.597. Both
had effectively zero strict TPR. The result does not contradict the causal
open proxy: it shows that global average pooling over source-labeled images
does not isolate the transferable signal and that SWT does not repair the
source shift.

Post-hoc image aggregation also failed to create an operating point. Averaging
presence logits raised AUC from 0.884 to 0.890, but increased strict test FPR to
0.77% while reducing TPR. Median, lower-quartile, upper-quartile, and top-tail
aggregation either preserved the overlap or suppressed almost every positive.
A separately trained binary presence head plus vendor head reached 0.880
ensemble AUC, 0.77% strict test FPR, and TPRs of 1.11% and 7.26%. Decoupling the
heads is architecturally faithful but insufficient without faithful labels.

These ablations close spectral feature engineering, naive full-field pooling,
and score aggregation as the next detector step. The next valid training epoch
requires same-content counterfactual pairs or independent watermark oracle
labels, matched transformations, and an image-level detection loss. External
generator corpora, including difficult non-target providers, remain hard
negative and FPR-challenge sets only.

### 2026-08-10: low-content controls and registered phase carrier

A same-resolution low-content matrix compared independently generated solid
outputs from two target model families against three per-image controls: exact
mean fill, amplitude-matched Gaussian noise, and a phase-randomized residual
with preserved Fourier magnitude. Raw stationary-wavelet summaries transferred
between the two target families with AUCs of 0.982 and 1.000, and reached 0.973
when blue and green were held out by color. This was not watermark evidence.
The frozen classifier accepted every one of 1,869 external negatives because
it had learned the distinction between real generator texture and artificial
controls. Removing absolute wavelet energy reduced external-negative
acceptance only to 61.6%, with similar 58.1-67.3% acceptance across all three
source classes. Both low-content wavelet branches are rejected as presence
detectors until real non-target solid outputs provide matched negatives.

The numeric V3 audit loader was then extended to support both dense and sparse
format-v2 profiles without pickle. Exact-profile evaluation exposed a sharp
encoder-version boundary. The 1024x1024 profile accepted none of 231 target
provider images and none of 26 exact-geometry negatives. The 1536x2816 profile
accepted 30 of 55 target-provider images, including all four temporal-test
images, while rejecting the one exact-geometry negative available in the
closed corpus. The independently fitted phase model accepted 24 of those 55
and also accepted all four temporal-test images. This is positive evidence for
a geometry- and epoch-specific carrier, not a universal SynthID decoder.

On the four temporal-test positives, the fixed V3 score survived JPEG-95 and a
75% downscale on all four images, survived JPEG-85 on two, and failed after a
5% center crop or a one-pixel translation on all four. Bounded analytical
translation registration recovered all four shifted images and selected the
known `(-1, -1)` offset. Searching up to 16 pixels produced no positives among
50 exact-resolution and 144 canonicalized frozen negatives. The shared
registration implementation now serves both the numeric V3 probe and the
independently fitted phase model.

A discovery-only scale-and-translation view search recovered all four 5%
cropped temporal images with the independently fitted model after lowering the
active-support gate from 0.50 to 0.40. It produced zero positives on the 194
frozen negatives and on the same preregistered 3,000-image COCO challenge used
by the identity scorer. The latter result has a zero-error one-sided 95% bound
of 0.0998% only for that abstention challenge: every COCO image remained
outside carrier support, with a maximum active fraction of 0.201. The scale
rule is not frozen because its support threshold was selected after inspecting
the crop examples. It requires a new temporal positive holdout before it can
join the detector rule.

The current actionable research candidate remains a positive-only,
provider-specific expert for the supported 1536x2816 carrier epoch. Identity
and bounded translation views use the frozen phase and support thresholds;
unsupported geometry, insufficient carrier magnitude, and ambiguous phase
return `abstain`. Vendor attribution may select the expert that supplied
accepted evidence, but it must not turn an abstention into a provider label.
The next calibration gate still requires at least 3,000 native-support
negatives, same-provider oracle negatives, matched non-target solid outputs,
and a new temporal positive that influenced neither profile nor threshold.

### 2026-08-10: 2048 periodic-tile detector

The phase hypothesis transferred to a second native geometry when the model
and operating point were kept separate. A 256-peak 2048x2048 model learned from
111 train positives used the already frozen phase threshold of 0.43, active
support threshold of 0.40, and a translation search of plus or minus four
pixels. It accepted 31 of 35 validation positives and 27 of 30 locked-test
positives while accepting none of 49 validation or 38 test negatives.
Translation registration recovered the shifted positives without changing
those identity counts. A threshold recalibrated from only 49 validation
negatives reached 30 of 30 test positives but accepted one test negative, so it
was rejected in favor of the transferred rule.

The wider native-geometry challenge exposed the remaining uncertainty. The
frozen 2048 rule accepted two of 182 earlier external-provider images, for two
accepted source negatives among all 269 native negatives. Both cases passed at
zero translation with high phase and support, and both also passed an
independently learned HSV phase branch. They are operational false positives
under source labels, but source provenance does not establish watermark
absence. They may instead expose a shared encoder or upstream backend. Without
an independent watermark oracle they cannot be relabeled either way. The same
experiment rejected the 1024x1024 and 768x1376 experts: they accepted 9 of 26
and 4 of 9 native source negatives, respectively.

The 2048 carrier has a concrete periodic mechanism. Its 256 peaks reduced to
108 unique spatial frequencies. Translating the frequency coordinates by 128
rows preserved 56 coordinates, while the maximum overlap in each of 1,000
uniform random controls was two. The permutation estimate was 0.001, and the
128-bin spacing implies a 16x16 spatial tile. A separate detector therefore
folded a high-pass residual modulo 16x16, averaged 16,384 repetitions, and
correlated the normalized tile against a train-positive template. After
float64 serialization and validation-only threshold calibration, the fixed
tile accepted 34 of 35 validation and 29 of 30 test positives, none of the 49
calibration or 38 held-out test negatives, and the same two of 182 earlier
source negatives. This second representation supports a real periodic carrier
rather than an arbitrary set of FFT peaks, but it does not resolve the two
labels.

The fixed tile also accepted none of a preregistered 3,000-image general-image
challenge after deterministic 2048x2048 canonicalization. The maximum
normalized correlation was 0.106 against a threshold of 0.174. The zero-error
one-sided 95% upper bound is 0.0998% for that challenge. Unlike the earlier
sparse-phase result, the tile score evaluates every image without a weak
carrier-support abstention. The challenge is still not native provider data
and cannot replace the required oracle-negative calibration.

Symmetric attack evaluation established the robustness boundary. The fixed
tile accepted 29 of 30 original test positives, all 30 after a 75% downscale
round trip, 21 after JPEG-95, three after JPEG-85, and none after a 5% crop,
with no accepted held-out negatives under the identity threshold. A
validation-calibrated JPEG-95 tile threshold recovered 27 of 30 but accepted
one of 38 test negatives. Requiring both codec-conditioned tile and phase
scores reduced JPEG-95 to 16 of 30 with no held-out-negative acceptance, but
still accepted one of the 182 earlier source negatives. The corresponding
JPEG-85 consensus accepted 5 of 30 positives and none of all 269 native source
negatives. Scale-and-translation phase search recovered 15 of 35 validation
and 14 of 30 test crops with no held-out-negative acceptance, but remains
discovery-only because the test transformation had already influenced the
branch. Low-frequency peak subsets and transform-augmented phase training
improved JPEG sensitivity only by raising validation false positives to
2-10%, so both were rejected.

The reproducible implementation is `scripts/synthid_periodic_tile_probe.py`.
It stores the normalized template in float64 and calibrates only after loading
the serialized artifact; an earlier float32 experiment moved a boundary score
by approximately 2.5e-10 and demonstrated why calibration-before-serialization
is invalid. The resulting research detector is positive-only and limited to a
confirmed 2048x2048 carrier epoch. An accepted expert may suggest the encoder
family, but the two cross-source carrier matches prohibit a stronger vendor
claim until an oracle distinguishes direct provider output from shared-backend
output.

A pixel-space ablation then tested whether the frozen tile merely predicted the
local scores or controlled them. At twice the train-median tile norm, aligned
subtraction changed the fixed-tile decision from 29 of 30 accepted originals to
zero and the independently fitted sparse-phase decision from 27 of 30 to zero.
The median fidelity was 53.74 dB PSNR and 0.99681 SSIM. Cyclically shifting the
same tile by one row and column left one phase acceptance, while a seeded
zero-mean random tile orthogonal to the learned template left 13; their median
PSNRs were within 0.13 dB of the aligned edit. For both local representations,
the aligned edit reduced the score more than either control on all 30 paired
images, with a two-sided sign-test p-value of 1.86e-9 for each comparison.
The same aligned edit reversed both local decisions on each of the two disputed
cross-source matches, while the orthogonal control left both phase decisions
accepted. That two-item result is descriptive but makes an accidental threshold
crossing less likely; it still cannot distinguish a shared carrier from direct
provider output.

This is the strongest local causal evidence for the 16x16 mechanism, but the
strength was selected after inspecting this locked test and is therefore
discovery-only. The shifted control also suppressed the phase representation
substantially, so local score reversal cannot certify signal removal. A matching
provider oracle must still compare untouched sources, aligned candidates, and
norm-matched controls before any removal claim. The reproducible local harness
is `scripts/synthid_periodic_tile_ablation.py`; its report records input and
model hashes without writing derivative images.

### 2026-08-10: confirmatory oracle-batch readiness

The corpus audit found no new 2048x2048 positive collected after the tile rule
and subtraction strength were frozen. Existing test images cannot be renamed as
a temporal holdout, so the confirmatory oracle batch remains blocked on new
provider output at the supported native geometry.

The batch mechanics are ready in `scripts/synthid_oracle_batch.py`. For each new
source, it preregisters five requests in a fixed order: untouched source,
lossless re-encode, aligned subtraction, cyclic-shifted subtraction, and an
orthogonal norm-matched tile. It refuses to write media inside the repository,
records artifact and decoded-pixel hashes, pins both model artifacts and the
matching provider, and detects any post-registration byte change. Oracle results
live in a separate manifest-bound file so the preregistration remains immutable;
the evaluator requires complete ordered results, verbatim responses,
timezone-aware timestamps, and separate SynthID and C2PA verdicts.

A causal success requires the source, re-encode, shifted, and orthogonal views
all to remain `detected` while only the aligned view becomes `not_detected`.
`Indeterminate` and refusal remain indeterminate. A one-source dry run on an old
test positive verified all five artifacts and the local scoring path, but is
pipeline validation only and contributes no confirmatory evidence.

### 2026-08-10: first confirmatory oracle attempt

Four new 2048x2048 Gemini outputs were generated after the local rule and
strength were frozen, then registered as a 20-request batch. The manifest and
all 20 artifacts passed hash verification before submission. The first source
group produced these ordered results:

| Role | Local tile/phase decision | Provider result |
| --- | --- | --- |
| source | detected / detected | SynthID indeterminate; Google C2PA present |
| re-encode control | detected / detected | Google AI signal detected |
| aligned subtraction | detected / not detected | Google AI signal detected |
| shifted control | detected / detected | Google AI signal detected |
| orthogonal control | detected / detected | refused: verification quota exceeded |

The quota response instructed the account to wait 24 hours. No adaptive retry
was made, and the remaining 15 preregistered requests were not submitted. The
batch cannot receive its preregistered aggregate verdict until complete ordered
results exist.

Even incomplete, this attempt rejects the frozen removal recipe for the first
temporal source: aligned subtraction crossed the phase threshold but remained
above the tile threshold and did not clear the provider oracle. The remaining
sources can still measure transfer and disagreement between the two local
experts, but they cannot turn this first aligned result into a universal
pixel-only removal success.

### 2026-08-10: positive-only runtime detector

Removal is deferred while the transferred tile signal is exposed as a bounded
detector. `src/remove_ai_watermarks/synthid_detector.py` loads the frozen model
as a bundled pickle-free runtime asset and returns `detected`, `not_detected`,
or `unsupported` without resizing input. The direct API and
`detect-synthid` CLI initially covered only native 2048x2048 images; `identify`
consumes a positive match as high-confidence evidence but never treats a
negative or unsupported result as proof of absence.

The operating point and model are unchanged from the locked experiment. The
detector accepted all four post-freeze Gemini outputs, including the source
whose frozen phase score missed, while retaining the prior 29-of-30 locked-test
sensitivity and zero accepted validation/test negatives. The unresolved two
external-source matches remain the reason a runtime positive names the carrier
but does not attribute a provider.

### 2026-08-10: calibrated native-geometry extension

The frozen 16x16 template and threshold transfer across the common native
geometries in the provider-positive evidence. Non-divisible image dimensions
use direct modulo folding with per-cell sample counts; divisible dimensions,
including 2048x2048, retain the original numerical path. All prior 2048x2048
records were replayed and matched exactly, including floating-point scores.

The runtime registry was expanded only after the unchanged threshold accepted
none of 60,000 public COCO challenge views, 3,000 at each of 20 target
geometries. This is a geometry extension of the same positive-only carrier
expert, not an OpenAI pixel detector or a proprietary payload decoder.

### 2026-08-11: calibrated image-size range

The fixed template was then evaluated on every provider-positive image in the
local evidence set rather than only its common geometries. It accepted 3,928 of
4,698 images across 757 exact geometries. Sensitivity separated by pixel count:
1,987 of 2,021 images at or above three megapixels crossed the threshold, while
1,940 of 2,672 images from one through two megapixels did. This establishes a
carrier-family boundary, not universal SynthID recall: explicit C2PA watermark
actions also occur below threshold, and three strong carriers use a different
cyclic phase.

Two public-image geometry challenges tested whether geometry itself creates
false matches. The first balanced 5,000 COCO images across all 757 observed
geometries, with every geometry present in both development and final partitions;
the maximum fixed score was 0.12549 and none crossed the unchanged 0.17357
threshold. The second transformed the same 5,000 source images at 256 generated
geometries from one through 18 megapixels, covering every width/height remainder
pair modulo 16. Its maximum was 0.16387 and again none crossed the threshold.
Runtime support therefore uses that challenged pixel-count interval instead of
an enumerated geometry registry, still without resizing.

A cyclic-registration branch was rejected after the public-image challenge.
At a low threshold it recovered 130 fixed-phase misses but false-fired on
tracked OpenAI and Adobe controls. Raising the threshold above all development
controls recovered only 23 in-range provider positives while adding 84
cross-source matches beyond the fixed detector. Three strong shifted Google
carriers remain a documented miss rather than weakening the runtime rule.

Top-level source labels were not treated as watermark-negative truth. Of 237
non-Google-labeled corpus images crossing the fixed threshold, 81 retained
SynthID provenance. High-scoring Adobe manifests explicitly named Gemini Flash
as the remote provider, and perceptual matching found direct Google derivatives
under editing or relabeling categories. The remaining source labels cannot prove
absence of the carrier, so they constrain provider attribution but do not justify
raising the pixel threshold.

### 2026-08-11: spatial-resampling boundary

Arbitrary decoded geometry did not imply arbitrary resize robustness. A
stratified sample of 80 fixed-positive provider images was rescaled in memory at
0.5, 0.625, 0.75, 0.875, 1.125, 1.25, and 1.5. The unchanged 16x16 detector
accepted none of the 80 images at every nonidentity scale. Restoring each view
to its source dimensions recovered 58-80, which isolates the failure to the
scaled sampling lattice rather than simple information destruction.

Scaling the template and modulo fold to the corresponding integer periods 8,
10, 12, 14, 18, 20, and 24 recovered 73-80 of the discovery images at the
native threshold. Searching all eight periods raised control scores, so a
single threshold was frozen above the maximum of 3,000 deterministically
resized COCO development views. It accepted none of 2,000 final controls and
672 of 800 source-disjoint provider positives, with 77-88 accepted at each
scale. Six tracked OpenAI and Adobe controls remained below the frozen threshold.

This did not generalize to arbitrary scaling. Factors 0.8, 0.9, 1.1, 1.2, and
1.333 create noninteger carrier periods; rounding the period accepted zero of
80 images in the fixed-phase branch at every factor, and cyclic registration
accepted only 1-16. Period-specific thresholds improved sensitivity but accepted
five of the 2,000 final controls. The integer-period bank is therefore retained
as a research result, not added to the runtime. A universal resize branch needs
fractional-period registration or reliable reconstruction of the pre-resize
geometry, followed by a new multiple-search calibration.

A discovery follow-up tested that fractional-period direction with the 30
strongest template harmonics. A continuous 7.5-24.5 spectral search placed the
true period within 0.05 pixels among its top three candidates for 58 of 60
transformed positives. Searching nine neighboring integer reconstruction
geometries recovered 44 of 60 at the native threshold; even the true source
geometry recovered only 48, so resampling damage sets a separate upper bound.
The full search then failed a frozen 250-development/150-final COCO challenge:
the calibration threshold accepted two final controls. A preselected product
of canonical correlation and spectral confidence increased positive
acceptance from 49 to 52 of 60 at its development threshold but accepted the
same two final controls. This fractional FFT baseline is rejected for runtime
use; better period estimation alone does not solve multiple-search specificity.

### 2026-08-10: OpenAI periodic-carrier challenge

The OpenAI track repeated the Google carrier method without runtime provenance
features. C2PA selected the research labels, but every candidate score consumed
only decoded RGB pixels. The temporally split corpus contained 4,615 OpenAI
training positives, 1,280 validation positives, 1,364 development-test
positives, 8,668 difficult external-source controls, and 3,000 COCO controls.
The development test is not called a locked holdout because earlier
representations had already exposed it.

High-pass residuals were folded modulo 8x8, 16x16, and 32x32 and normalized as
in the Google fixed-tile expert. A single 16x16 OpenAI template accepted only
one of 1,280 validation positives at the threshold above all 2,287 validation
controls. A 16-template geometry bank improved that to 12 positives but
accepted one of 3,372 development-test controls. The corresponding
development-test sensitivity was 9 of 1,364. The frozen Google template did
not transfer: at its unchanged threshold it accepted 14 validation positives
and 572 validation controls.

The apparent native-size signal was a confound. At 1024x1536, 91.6% of the
learned template energy projected onto a 2x2 periodic lattice, compared with
5.6% for the frozen Google template. Firefly, China AIGC-labeled, local
diffusion, and unidentified hosted-generator controls reached correlations of
0.92-0.98 against the uncorrected OpenAI template. This is operational evidence
for a shared decoder or upscaler lattice, not an OpenAI watermark carrier.

Projecting the 2x2 nuisance lattice out of every 16x16 fold isolated a weaker
epoch-specific residual. The 1024x1536 expert accepted 5 of 55 validation and
10 of 51 development-test positives while accepting none of the full
validation or development-test controls. Nine of the ten development-test
matches occurred from July 12 through July 14; later dates contributed only
one of 27. The 1536x1024 expert accepted 6 of 37 validation and 2 of 51
development-test positives with no development-test controls. Amplitude,
active-support, channel-consensus, payload-invariant power, and spherical
multi-template branches did not improve this frontier without false positives.

The OpenAI branch therefore remains research-only and is not added to the
runtime detector. The next valid training epoch requires same-content
OpenAI-oracle `detected` and `not_detected` pairs, or provider-authorized decoder
labels, followed by a fresh temporal holdout. Source provenance alone cannot
distinguish a true watermark carrier from the measured generator lattice.

### 2026-08-10: OpenAI content-dependent decoder challenge

The periodic result did not exhaust the neural-watermark hypothesis. OpenAI's
ChatGPT Images 2.0 system card describes its watermark as content-specific, and
the SynthID-Image paper says the encoder is content-dependent by design. The
paper also separates watermark detection from payload recovery and evaluates
the external SynthID-O model at its preferred 512x512 input size. These facts
support a learned full-field decoder, but they do not establish that OpenAI and
Google deploy identical model weights, payloads, or pixel spectra.

A second corpus audit found 261 same-provider candidate controls. Their signed
provenance contained `created` and `converted` actions without the
`c2pa.watermarked.unbound` action, but a subsequent software-agent audit showed
that they do not all come from the positive generation epoch. Only 118 name
`gpt-image 2.0`: 97 training, 16 validation, and five development-test images.
Another 108 name an earlier version and 35 do not expose a usable version. The
full 261-image split remains 217/26/18. These are useful confound controls, but
even the exact-version subset is action-derived rather than a provider-oracle
negative label.

Two pixel-only native-resolution experts were trained with the mixed-version
control set. A
local residual CNN accepted 132 of 1,280 validation positives and 149 of 1,364
development-test positives, with zero same-provider or COCO controls in both
splits and two of 1,373 difficult development-test controls. A separate
spectral, autocorrelation, bit-plane, and residual-error expert accepted 175
validation and 167 development-test positives with no accepted controls. A
validation-selected linear combination accepted 243 positives in each split,
with no accepted validation or development-test control. The zero-error
development-test bound across 3,391 controls is 0.0883% at one-sided 95%
confidence, but the same-provider subset contains only 18 images and therefore
does not independently establish provider specificity.

The exact-version audit did not invalidate the native score counts, but it
weakened their attribution. None of the 16 validation or five development-test
`gpt-image 2.0` controls crossed the residual, forensic, ensemble, canonical,
or JPEG-equalized thresholds. That is directionally useful, but five temporal
test controls cannot establish deployment specificity. Perceptual-hash and
local CLIP searches compared all 118 exact-version controls with 7,259
positives. They recovered a few near-content matches but no clean before/after
watermark pair. Sub-pixel affine alignment left content, edge, and photometric
changes in the residual, while 8x8, 16x16, and 32x32 folded residual
correlations varied in sign and magnitude. Those candidates cannot be used as
causal watermark differences.

Transformation challenges rejected the combined native expert as a SynthID
decoder. Of its 243 accepted development-test positives, 121 remained accepted
after a 5% crop round trip, six after a 75% resize round trip, and none after a
JPEG-95 round trip. No transformed same-provider control was accepted. The
codec fragility is inconsistent with treating the score as the documented
robust watermark without further evidence.

The 512x512 branch also failed the held-out specificity gate. Its selected
model accepted 238 validation and 194 development-test positives, but also
accepted two of 18 same-provider, four of 1,373 difficult, and nine of 2,000
COCO development-test controls. Finally, a CNN trained and evaluated only
after applying the same JPEG-95 round trip to every positive and control
accepted eight validation positives and six development-test positives while
accepting five of 2,000 development-test COCO controls. Equalizing the codec
therefore removed nearly all of the apparent signal instead of revealing a
robust hidden decoder feature.

An independent three-CNN OpenAI surrogate was also evaluated from its
published weights, without adopting its code or claims. At the published 0.5
threshold its ensemble marked 82.0% of COCO validation controls and 83.4% of
COCO development-test controls as watermarked. It also marked 56.3% of
difficult development-test controls and 15 of 16 exact-version OpenAI
validation controls, compared with 87.3% of OpenAI validation positives. The
repository does not publish its training corpus or logs, and its implementation
applies supposedly shared pair augmentation independently. This result rejects
the model as a SynthID decoder and demonstrates why same-content-looking
regenerations are not sufficient negative labels.

A final transform-augmented full-field branch tested the closest practical
approximation to the documented neural decoder. A 512x512 CNN consumed both
RGB and a fixed high-pass residual and trained with random crop/resize,
JPEG 70-100, horizontal flip, and mild color transforms. Training sampling
balanced watermarked positives, difficult controls, and the exact-version
OpenAI candidate controls. Selection required a score above every control for
both native and JPEG-95 validation views. All four fixed training epochs
accepted zero of 500 selection positives. On the full validation set the
frozen model accepted zero of 1,280 OpenAI positives in native, JPEG-95,
75%-resize, and 5%-crop views, while accepting up to two unrelated controls.
On development test it accepted zero of 1,364 OpenAI positives in native,
JPEG-95, and resize views. The crop view accepted one OpenAI positive and one
of 1,373 difficult controls. Transform augmentation therefore did not recover
a usable weaker OpenAI signal.

The measured OpenAI-native separation is best classified as an export or
rendering noiseprint, not a validated SynthID detector. None of these models is
added to runtime. Transform-augmented training has now also failed. A
defensible next epoch needs provider-authorized labels or clean same-content
before/after watermark pairs, plus a fresh temporal holdout that has not
influenced representation or threshold selection.

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
- OpenAI, [ChatGPT Images 2.0 system card](https://deploymentsafety.openai.com/chatgpt-images-2-0/automated-evaluations-and-adversarial-testing).
- Google, [Verify AI-generated images, videos, and audio](https://support.google.com/gemini/answer/16722517?hl=en).
- Gowal et al., [SynthID-Image: Image watermarking at internet scale](https://arxiv.org/abs/2510.09263).

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

### 2026-08-13: external V4 cross-color codebook audit

The later `aloshdenny/reverse-SynthID` V4 artifact was audited independently at
commit `b110836`. The audit read only numeric NPY members from its NPZ ZIP with
pickle disabled and reproduced the published native-resolution phase score;
no third-party Python or pickle payload was executed. Its bundled
`sample_watermarked.png` crossed the documented `phase_match > 0.52` threshold
at `0.535`, confirming that the reproduction follows the intended path.

The operating point did not transfer. Taking the better of the two published
model profiles detected 141 of 355 Google positives and 191 of 499 controls.
On a later frozen 1,000-image Open Images reserve it accepted 386 controls. The
phase score had AUC 0.517 on the paired corpus. Reproducing the July 2026 GUI's
0.3%-aspect-ratio gate reduced coverage without adding discrimination: it
supported 121 positives and detected 46, while supporting 343 controls and
detecting 132; it also detected 284 of 685 supported fresh controls.

The failure follows directly from the metric. Per-bin phase similarity is
`1 - abs(wrapped_difference) / pi`, whose expectation under independent uniform
phase is 0.5, only 0.02 below the threshold. The detector selects bins by
cross-color phase coherence alone and does not require image-side carrier
amplitude or a content-baseline excess. Its selected bins span nearly the full
spectrum, with a typical spatial period around 2.5 pixels. Cross-color
coherence is useful for discovering candidates from genuinely low-texture
references, but this single-image score is not a calibrated detector.
Two prespecified rerankings did not rescue it. Restricting carrier periods to
4-128 pixels and ranking by either coherence times reference magnitude or the
stored carrier weight times reference magnitude produced best-of-model AUCs of
0.521 and 0.524. They were evaluated as continuous scores without selecting a
new test-set threshold and are also rejected.

The repository's older V3 phases also failed this external challenge. Their
best dark/white phase score had AUC 0.473; the documented 0.78 phase threshold
accepted 5 of 355 positives, 5 of 499 controls, and 6 of the later 1,000 fresh
controls. The repository's current bundled sample and four validation sources
all remained below that phase threshold. The README's accuracy claim is
therefore not accepted as evidence for the current corpora.

The linked Hugging Face dataset cannot repair OpenAI calibration as published.
Its DALL-E 3 `black` and `white` buckets are not solid-color probes: per-image
mean luminance ranged from 11.66 to 143.74 and 124.94 to 235.66 respectively.
Across ten 1024-square images per bucket, only 39 and 32 RGB frequency bins had
phase coherence above 0.9, versus 20,443 and 100,252 for the corresponding
Gemini 3.1 buckets. Only four DALL-E bins cleared 0.9 in both colors and all
four were trivial DC or self-conjugate-axis coordinates; Gemini had 11,478
nontrivial joint bins and 3,341 also had cross-color absolute-cosine agreement
above 0.9. Those DALL-E folders measure heterogeneous content phase, not an
OpenAI solid-reference codebook. The official SynthID-Image paper also says
nearly uniform corner cases may be excluded from watermarking, so generating
flatter references does not guarantee a stronger watermark. A useful next
external experiment requires newly collected low-content OpenAI outputs whose
pixel watermark is separately confirmed, plus same-provider oracle-negative
controls, before freezing any phase bins.

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

A later exact-1024 content audit found that perceptual siblings can cross an
image-level fit split even when file and decoded-pixel hashes differ. The local
2048 reports retain aggregate counts and model hashes but not the 111 fitting
paths, so the old train/validation/test split cannot now be audited for that
specific leakage mode. This does not invalidate the independently collected
general-image challenges or justify changing the frozen runtime model, but the
reported positive rates remain conditional on the historical split. Any next
model calibration must retain content-group membership and prove that no group
crosses train, validation, test, or temporal partitions.

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

### 2026-08-12: fast adaptive carrier projection

The fixed twice-median subtraction was intentionally conservative but spent
substantially more pixel norm than many images needed. A follow-up tested a
one-dimensional per-image solver. For source pixels `x`, frozen unit carrier
`t`, and scalar amplitude `a`, the candidate is
`clip(round(x - a * tile(t)))`. A bounded scalar search selects the smallest
`a` that reaches the local target. This is a direct pixel edit: it uses no
generative decoder, does not resize the image, and searches one scalar rather
than optimizing a full-resolution tensor.

The first challenge reused the 30 historical 2048x2048 causal-ablation
sources. Three were not simultaneously positive under the fixed-tile and
independently fitted phase rules and were excluded before counting a reversal.
All 27 conjunctive positives cleared both local rules after adaptive
subtraction. Median PSNR was 59.83 dB and median SSIM was 0.99890; the minima
were 55.19 dB and 0.99705. Repeating the same selected amplitude with a
one-row, one-column cyclic shift cleared zero of 27. Sixteen original images
remained conjunctively positive after JPEG-95. The aligned candidates cleared
all 16 after the same round trip, while the shifted controls cleared one. This
improves materially on the earlier fixed-strength median of 53.74 dB without
weakening the local causal control.

A three-image pilot also compared subtracting the complete per-image folded
high-pass residual and a regularized inverse-high-pass reconstruction. Both
could clear the two local scores, but their selected candidates retained only
about 54-57 dB PSNR, compared with 59-62 dB for the frozen carrier projection
on the same images. Removing the whole folded residual therefore spends pixel
norm on content-correlated periodic structure and was rejected in favor of the
narrow carrier direction.

The geometry challenge then selected three `first_only` carrier positives from
each of the 20 most frequent native Spaces geometries. The edit repeats the
same 16x16 carrier past the image boundaries and crops the repetition to the
decoded dimensions, so it does not require dimensions divisible by 16. A zero
score target cleared 60 of 60 aligned candidates and 5 of 60 matched shifted
controls. Median PSNR and SSIM were 60.37 dB and 0.99919; the minima were
53.56 dB and 0.99581. These samples come from an already inspected detector
corpus, so they measure mechanism transfer across geometry rather than fresh
detector or removal generalization.

The zero target left one WebP-95 and eight resize survivors among transformed
sources that were still locally positive. A frozen follow-up used a target
score of -0.25. It cleared all 60 native candidates at median 57.70 dB PSNR and
0.99863 SSIM, with minima of 52.38 dB and 0.99443. Conditional on the matching
transformed source remaining above the fixed carrier threshold, the aligned
candidate cleared 32 of 32 JPEG-95, 13 of 13 JPEG-90, 8 of 8 JPEG-85, 15 of 15
WebP-95, and 54 of 54 0.75x resize round trips. The corresponding one-pixel
shifted controls cleared 7, 1, 1, 5, and 17. The increased shifted-control rate
is the measured price of adding transform margin.

The frozen -0.25 recipe was finally run once on one deterministic first-carrier
positive from every represented native Spaces geometry. All 647 images at 647
distinct decoded sizes reached the target, with no maximum-amplitude failure.
Median fidelity was 57.67 dB PSNR and 0.99867 SSIM; the worst case was 51.78 dB
and 0.99400. Of 323 source images whose carrier survived JPEG-95, 323 aligned
candidates and 58 shifted controls cleared after the same round trip. Natively,
153 of 647 shifted controls also cleared at this deeper margin. The consistent
aligned result supports geometry-independent control, while the increased
shifted rate shows that the conservative edit perturbs a wider neighborhood of
the periodic carrier. Because the all-geometry corpus had already influenced
detector research, it is a coverage challenge rather than a fresh holdout.

This is a fast local carrier suppressor, not a verified SynthID remover. The
earlier Google oracle remained positive after analytical edits that already
looked favorable to local models, and the adaptive scalar recipe has not been
submitted to a matching-provider oracle. Provider terms and the project oracle
policy also prohibit turning verifier responses into an adaptive search loop.
The next valid test is one preregistered source/re-encode/aligned/shifted batch
at a healthy authorized oracle, with the amplitude rule and -0.25 target frozen
before submission. Until that batch returns a matching-provider negative result,
no production command exposes this method as removal.

The reproducible implementation is
`scripts/synthid_adaptive_carrier_suppress.py`. It writes only lossless PNG,
refuses overwrite and locally negative input, and records source/output hashes,
the selected scalar amplitude, local scores, fidelity metrics, and runtime in a
sidecar JSON report. Unit tests cover non-divisible geometry, target attainment,
an unreachable target, and the negative-input guard. A real CLI smoke test on a
Spaces source reproduced its reported score exactly through the runtime detector
after saving. It remains a research script rather than a routed package command.

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

### 2026-08-11: multiscale calibration and opt-in registered detector

The fractional search was revisited as a multiple-search calibration problem,
not as period estimation alone. A source-disjoint challenge used 200 confirmed
fixed-carrier positives, 40 independent sources at each scale 0.8, 0.9, 1.1,
1.2, and 1.333. Controls were 4,900 unique COCO images resized into the positive
pixel-count domain, split into 2,900 development and 2,000 final items. The ten
frozen candidates combined exact fractional canonical correlation, quadrant
agreement, and a three-level scale-space score through mean or minimum rules.
Pure box-counting dimensions, multifractal width, lacunarity, roughness,
wavelet-energy slope, and a generic log-Mellin response had already failed the
smaller pilot and were not promoted to the large challenge.

At the development-only threshold, the three-way mean accepted 177 of 200
positives versus 163 for canonical correlation alone, with 16 positives rescued
and two lost in the paired decision. Each produced one final false positive, on
different source images, so the development threshold was rejected. Recalibrating
above all 4,900 COCO controls left 176 of 200 three-way positives and 160 of 200
canonical-only positives. This recalibration is exploratory rather than a new
validation because the final controls had then been inspected.

A second source-disjoint corpus froze those thresholds before scoring 105 new
positives across scales 0.5, 0.65, 0.8, 1.0, 1.2, 1.333, and 1.5, plus all 879
content-deduplicated Kodak and Picsum controls available locally. Natural
2816x1536 controls had a heavier null tail than upscaled COCO: the three-way
mean accepted 82 of 105 positives and six controls at the COCO threshold,
whereas canonical-only accepted 79 positives and ten controls. A threshold
above all 5,779 controls retained 253 of the first 305 positives for the
three-way mean. Four coarse pixel-count bins recovered only six more positives,
so size normalization did not explain the main 0.5x miss.

At 0.5x, a fixed period-8 branch raised canonical correlation for seven of the
15 discovery positives but also won the unconstrained search on 629 of 879
controls. Searching it unconditionally merely raised the null threshold. The
frozen remedy requires period-8 native correlation of at least 0.35 and takes
the maximum of the old and period-8 three-way scores. It added four positives
without an accepted control in the discovery corpus. On the earlier 4,900
controls, the frozen gate never opened and none crossed the final three-way
threshold `0.2460603834083705`.

The improvement itself was then tested on 50 additional source-disjoint 0.5x
positives that influenced neither gate nor threshold. The ungated three-way
score accepted 6; the frozen gate accepted 17, rescuing 11 and losing none. The
exact paired sign test was `p = 0.0009765625`. These results support an opt-in
scale-registered detector over 250,000 through 10,000,000 decoded pixels. The
runtime also requires both sides to be at least 64 pixels so each canonical
quadrant can retain a full 16-by-16 tile. These results do not establish a
universal SynthID decoder: the control maximum helped set the operating point,
33 of 50 new 0.5x positives still missed, and crop, strong codec changes, other
carrier epochs, and provider attribution remain outside the claim. The fast
native fold remains the default and the `identify` path.

That period-8 conclusion was overturned by a later symmetric negative test.
Every one of the 11,506 known non-Google Spaces controls was downscaled by 0.5,
matching the positive transformation; 11,273 outputs remained in the registered
geometry range. The direct analytic 8-by-8 template was dominated by shared
resize structure: 80.8% of its energy projected onto a 2-by-2 lattice and 94.0%
onto a 4-by-4 lattice. The production period-8 gate opened on 73 controls, and
all 73 crossed the registered threshold. They spanned hosted jobs, Firefly,
China AIGC-labeled generators, Meta-tagged images, OpenAI, and local tools. No
tested secondary condition separated the 11 rescued positives from those 73
controls. The explicit period-8 rescue is therefore rejected and not part of
the runtime detector. The 0.5x rescue result is retained here as an incident
record against asymmetric transformed-positive evaluation.

The same symmetric corpus also invalidated the main single-threshold registered
rule: 68 of 11,273 supported controls crossed `0.2460603834083705`. Fixed
thresholds for nine recovered-period bins eliminated those errors while
retaining 238 of 355 transformed positives, but one of 4,900 COCO controls then
crossed through the third spectral candidate. Requiring the canonical winner to
match the strongest spectral candidate removed that case and all 68 Spaces
errors, with 239 of 355 positives retained. This version was not shipped: a
fresh, content-deduplicated 1,000-image Open Images validation corpus produced
six false positives.

All six Open Images errors concentrated their apparent match in one
middle-frequency ring. Their correlations disappeared or changed sign in the
two higher-frequency rings of the 16-by-16 carrier, unlike the accepted Gemini
positives. Adding a frozen minimum correlation of `0.075` across those two rings
removed the six development errors and retained 229 of 355 positives. A
previously untouched reserve of 499 supported Open Images controls then produced
five amplitude-gate candidates and zero final positives; their maximum
high-band score was `0.004682175209264222`.

The retained positives by scale were 0/65 at 0.5, 8/15 at 0.65, 53/55 at 0.8,
33/40 at 0.9, 13/15 at 1.0, 30/40 at 1.1, 38/55 at 1.2, 40/55 at 1.333, and
14/15 at 1.5. A physically transformed template recovered strong correlations
for some period-8 positives, but 975 top-candidate Spaces controls fully
overlapped every tested amplitude, spectral-band, and joint feature. No
zero-control operating point retained a period-8 positive. The calibrated
runtime therefore uses the top-candidate, period-bin, and high-band gates and
makes no 0.5x detection claim.

An exploratory amplitude-times-high-band rescue later tested whether the two
existing gates could trade evidence instead of both passing independently. A
threshold frozen above all 341 top-1 development controls recovered 11 of the
126 current false negatives and accepted none of a separate 499-image Open
Images reserve; the reserve maximum was 0.100583 against the 0.118168
threshold. The decisive symmetric challenge rejected it: 19 of all 11,506
Spaces controls after 0.5x resizing crossed the frozen threshold, with a
maximum of 0.179989. The errors spanned OpenAI, Firefly, Microsoft, hosted
jobs, and other generators. Raising the threshold post hoc above that maximum
would recover only seven false negatives, none at scale 0.65 or 0.8. The joint
rescue is rejected; the independent amplitude and high-band gates remain the
measured operating point.

### 2026-08-13: public bypass corpus and inverse-carrier audit

The public `cebeuq/Synthid-Bypass` V2 comparison set supplied 12 external
before/after pairs produced by a diffusion reconstruction workflow. The fixed
runtime carrier accepted 10 of 12 `before` images and none of the 12 `after`
images. The two misses were not assumed negative: Gemini Verify AI reported
SynthID on `before/03.webp` and `before/07.png`, and no SynthID on both paired
outputs. Outputs `01` through `06` were also oracle-negative; the verifier's
daily limit stopped the same-session sweep at `08`.

`07.png` is a low-SNR instance of the shipped positive direction. Its full-frame
score was `0.1248368819`; its signed RGB correlations were 0.073, 0.183, and
0.111, and all nine aligned region scores were positive. A proposed rescue at
`score >= 0.12` with Green dominance and spatial agreement separated it from
the two highest transformed-COCO controls, but failed a fresh exact-1024 Open
Images challenge. A 2009 natural photograph scored `0.2123730698`, had stronger
Green dominance and nine-region agreement, and Gemini returned `SynthID not
detected`. The downloaded bytes matched a fresh fetch from the official Open
Images validation bucket. This is a confirmed runtime false positive, not a
provider-label inference.

The failure is broader than that one JPEG. Symmetrically resizing the 24 Kodak
PNG controls to 1536 by 2752 with Lanczos produced fixed scores as high as
`0.3768339306`. Those synthetic views were not used as independent clean
samples, but they prove that rational resize lattices can create a stronger
signed 16-by-16 match than the runtime threshold. The existing 5,000-view
observed-geometry and 5,000-view generated-geometry COCO challenges remain
valid for their exact source-and-transform assignments; they do not justify a
universal transformation claim. No threshold relaxation for `07` is allowed,
and the current direct detector needs a fresh source-and-transform-grouped
specificity epoch before its support range can be broadened.

`03.webp` tested a different hypothesis. The two content-group-separated
alternate-Gemini experts both rejected it. Its shipped-template score was
instead `-0.3263447029`, all three channel scores were below `-0.28`, and every
one of nine aligned regions was negative. The paired oracle-negative output
weakened to `-0.1531420136`. Neither 5,000-view COCO geometry challenge nor the
fresh Open Images blocks contained a score at or below `-0.20`, making the
opposite-polarity response a plausible additional codeword or provider state.
It is not specific enough to ship: 40 of 11,506 heterogeneous non-Google-labeled
AI controls crossed `-0.20`, with examples from OpenAI, Microsoft, multiple
other generators, and unassigned made-with-AI files. An inverse-template expert
therefore remains a research hypothesis until matching-provider oracle labels
and a new untouched natural and AI control split exist.

A follow-up decomposed the two high-frequency rings instead of taking their
minimum. The 19 joint-rule false positives were broad-band, with median
`min(ring) / max(ring)` of 0.84, while the registered false negatives had a
median of 0.27. A development-selected rescue therefore multiplied normalized
amplitude by the stronger ring and required ring balance at or below 0.5. A
threshold above 341 development controls recovered 11 of 65 top-1 false
negatives and accepted none of the 499-image Open Images reserve. The full
symmetric challenge again rejected it: 13 of 11,506 resized Spaces controls
passed, with a maximum score of 0.694818 against the 0.308683 threshold. Strong
single-ring lattices occurred in Firefly, OpenAI, hosted jobs, China-labeled
generators, Canva, and other controls. Radial imbalance is therefore another
general renderer or resize feature, not a SynthID-specific rescue.

A multi-codeword hypothesis then projected the shared 16-by-16 template out of
each normalized residual tile and fitted source-disjoint spherical codebooks to
the remaining 768-dimensional vectors. Five prototypes selected on 300
positives retained 366 of 600 held-out positives. Three prototypes were highly
reproducible across an independent 300-positive fit, with matched correlations
of 0.88 through 0.95, while the additional states were less stable. A threshold
above 2,500 development natural-image controls accepted none of a separate
2,500-image reserve and selected 225 of 770 metadata-labeled Google images that
the shared-template threshold missed. The broader challenge decisively rejected
the feature: 828 of 11,506 metadata-labeled non-Google Spaces controls crossed
the frozen threshold. Errors occurred across OpenAI, Microsoft, Firefly,
China-labeled generators, hosted jobs, Stable Diffusion, and other sources. A
post-hoc intersection above every control that also passed the registered
min(R, B) gate retained 138 Google candidates, but none passed that independent
carrier gate. The residual clusters are reproducible generator or resampling
structure, not a specific additional SynthID codebook, and are excluded from
runtime.

A related spatial-payload pilot stopped averaging all 16-by-16 blocks and
measured carrier and codebook responses block by block. The positive carrier
response was spatially coherent: median adjacent-block correlation was 0.61 on
both axes, compared with 0.20 and 0.24 in a heterogeneous Spaces sample and
0.04 and 0.06 among codebook false positives. The development-selected rescue
was instead the standard deviation of the best codebook response across
blocks. It retained 11 of 60 reserve positives and none of 180 reserve controls,
but accepted six of 1,000 fresh heterogeneous controls. Those errors included
OpenAI, hosted, and China-labeled generators; raising the threshold above their
maximum retained only four of the 120 pilot positives. Per-block carrier or
codeword coherence is therefore diagnostic but not a usable rescue.

A geometry-stratified follow-up found a second reproducible native 16-by-16
carrier in the fixed-template misses. Templates fitted independently from two
halves of the 1024-by-1024 misses correlated at 0.869, and two independent fits
from the non-1024 misses correlated at 0.956. The latter correlated 0.82-0.84
with the 1024 template but only about 0.28 with the shipped carrier. This rules
out a single-resolution averaging accident and supports a distinct carrier
direction or state.

The initial 1024 template retained 8 of 91 held-out misses and accepted none of
81 exact-geometry reserve controls or 500 natural-image reserve controls. Seven
of those eight positives survived JPEG 95, six survived JPEG 85 and 70, and
three survived a 0.75x resize round trip; WebP 95 retained none. A threshold
frozen above the exact-geometry development controls accepted 25 of 11,506
heterogeneous controls when applied at arbitrary native geometries, so an
unrestricted second native template is rejected. Canonicalizing every control
to 1024 by 1024 eliminated all 11,506 errors, and the same path accepted only
the native 1024-by-1024 Google misses. The signal has a fixed native period,
not a size-normalized frequency.

A stricter chronological fit used only 1024-by-1024 misses through mid-June and
tested July misses. Its template correlated 0.839 with the independently fitted
July template, retained 5 of 95 temporal misses, and accepted none of 81 reserve
exact-geometry controls. At that frozen threshold, canonicalization accepted 18
of all 770 fixed-template Google misses and none of all 11,506 heterogeneous
controls; every accepted miss was natively 1024 by 1024. Requiring agreement
between two independently fitted early templates retained three temporal
misses and no reserve controls. This is credible evidence for a second carrier
direction within the Google cohort, but the positive and exact-geometry control
counts are still too small for a runtime operating point. The later external
natural-image challenge below further shows that this repeatability is not yet
specific enough for blind detection.

Projecting the shipped carrier out of every normalized tile did not remove the
second direction. The early orthogonal template was numerically orthogonal to the
shipped template, correlated 0.834 with an independently fitted July orthogonal
template, and retained the same 5 of 95 temporal misses with none of 81 reserve
exact-geometry controls. Its threshold was frozen above the development controls
before the decisive 1024-by-1024 canonical challenge; none of all 11,506
heterogeneous controls crossed it, and the maximum remained just below the
frozen boundary. The second direction is therefore not a weak projection of the
shipped carrier. This strengthens the research finding but does not enlarge the
small temporal-positive or exact-geometry control reserves required for runtime.

Mapping both frozen scores over all 4,698 Google-labeled images changed the
interpretation from an epoch replacement to coexisting carrier states. The map
contained 3,825 first-only, 69 second-only, 103 both, and 701 neither cases;
the two scores correlated at -0.563. Both directions occurred throughout the
collection interval and across multiple native geometries, while the presence
of both in 103 images rules out a simple dated switch from one template to the
other. The second native threshold remains exploratory outside exact
1024-by-1024 inputs because 8 of 11,506 heterogeneous native controls crossed
the orthogonal version's threshold; only the canonical exact-geometry challenge
retained the zero-of-11,506 result.

Freezing a stricter native threshold above the maximum of 5,753 alternating
development controls left zero crossings in the other 5,753 controls and 26
Google images missed by the first carrier above threshold. That retrospective
split is promising but not a certified operating point: the corpus had already
been inspected while developing the second carrier, so a fresh source- and
time-disjoint challenge is still required.

An external natural-image challenge then rejected that strict native threshold.
It accepted none of 1,500 unique Open Images controls and none of 12 Wikimedia
controls, but one of 637 content-deduplicated Picsum controls. The original
Picsum directory contained 1,000 filenames but only 637 unique hashes; the one
crossing appeared twice under different ids and is counted once. Its RGB and
quadrant contributions were highly uneven, unlike the small temporal-positive
set, but that post-error observation cannot retroactively define a gate. The
strict native threshold remains excluded from runtime.

The original exact-1024 threshold also failed on those external controls: four
of 1,500 Open Images and four of 637 unique Picsum images crossed it, including
native 1024-by-1024 cases. The earlier zero-of-11,506 canonical result was
therefore specific to that heterogeneous control composition, not evidence that
exact geometry alone makes the carrier specific. Requiring agreement between
the two independently fitted early templates did not close the gap; it retained
three temporal positives but accepted one Open Images and two unique Picsum
controls. The second direction remains a reproducible Google-cohort signal, not
a blind detector.

Requiring the orthogonal score to survive a JPEG-95 round trip was not a
specificity gate either. It retained four of the five temporal positives but
also retained all four Open Images and all four unique Picsum crossings at the
original threshold. The natural-image confound is itself transport-stable.
Together with the failed low-rank, two-template, channel-balance, quadrant, and
two-carrier-plane variants, this exhausts mean-template consensus for the
second direction on the current data.

The orthogonal carrier is not a cyclic shift or color permutation of the
shipped template. Its best absolute cyclic correlation was 0.212, Fourier
magnitude correlation was 0.480, and weighted phase lock was 0.200. Dominant
frequencies were axial, led by `(0, +/-8)`, `(0, +/-3)`, and `(0, +/-5)` rather
than the first direction's broader structure. A horizontal-axis-only ablation
retained all five temporal detections and no reserve exact-geometry control, but
then accepted three of the 11,506 canonicalized heterogeneous controls. The
errors included an OpenAI-labeled image and two watermark-remover outputs. The
full orthogonal template is more specific than its strongest axial component.

A final low-rank variant tested whether that direction contains several payload
states rather than one mean carrier. SVD bases of ranks 1, 2, 3, 4, 6, 8, 12,
and 16 were fitted only on early 1024-by-1024 misses. Rank was selected on a
separate June interval and a separate control third, then reported on July
misses and the final control third. The selected rank 12 retained 2 of 38
validation misses and 4 of 95 test misses, with no control error. Rank 2 happened
to retain 6 test misses but only one validation miss and therefore could not be
selected without post-test tuning. A multi-state subspace did not improve the
evidence-grade operating point.

Deflation then tested whether a third stable linear carrier remained. After
projecting both the shipped and second orthogonal templates out of every
normalized tile, early and July residual averages correlated only 0.0003. The
early residual template retained none of 95 temporal misses and none of 81
reserve exact-geometry controls. Within this 1024-by-1024 temporal corpus, the
linear periodic model therefore supports two reproducible carrier directions,
not an open-ended sequence of mean templates.

Treating those directions as a single two-dimensional carrier plane did not
provide a safer weak-signal rescue. A positive-quadrant Euclidean norm used the
two independently frozen carrier thresholds as axis scales, then froze its own
boundary above 81 exact-geometry development controls. It rescued none of the
Google images below both component thresholds and accepted one of 81 reserve
controls. The two directions must retain separate operating points; combined
subthreshold energy is rejected.

The five temporal positives above the original second-carrier threshold also
had unusually balanced normalized R, G, and B contributions: their worst
channel ranged from 0.297 to 0.320, while seven of eight native control errors
were below 0.297 and were commonly blue-heavy with a weak green contribution.
A clean chronological validation did not justify turning that observation into
a gate. A template fitted on half of the early positives produced no accepted
examples in the other early half at the threshold frozen from development
controls, despite accepting six July examples and no reserve control. The
channel-balance rule is therefore a post-test hypothesis, not detector logic.

A phase-only follow-up removed observed Fourier magnitude and averaged phase
agreement using only the early template's fixed spectral-energy weights. The
phase threshold alone retained 2 of 31 early validation misses and 10 of 95
July misses, but accepted one of 81 reserve exact-geometry controls. Requiring
both phase agreement and the independently calibrated linear projection
removed that control error and all external natural-image errors. The frozen
conjunction retained 1 of 31 early validation misses and 3 of 95 July misses,
accepted none of 162 heterogeneous exact-1024 controls, none of 1,500 unique
Open Images, none of 637 unique Picsum images, and none of 12 Wikimedia images.
Applied outside its declared geometry it accepted 3 of 11,506 heterogeneous
native controls, all at non-1024 sizes. This is the first independently
challenged phase-and-amplitude candidate for the second direction, but three
temporal positives are not enough to ship a runtime branch.

Across all 443 exact-1024 Google images, the frozen conjunction found 11 that
the shipped carrier missed and 16 that both branches accepted; 244 were found
only by the shipped carrier and 172 by neither. The candidate therefore adds
signal rather than merely confirming the first direction, but its incremental
native recall is still small.

Swapping the two early fit halves and recalibrating both thresholds retained 4
of 31 opposite-half validation misses and 4 of 95 July misses, again with none
of 81 reserve exact-geometry controls passing the conjunction. This supports
fit-split signal reproducibility, but the swapped operating point accepted one
of 92 unique exact-1024 Open Images controls in its external challenge; none of
637 unique exact-1024 Picsum controls crossed. A post-hoc consensus of the two
fit halves would require another untouched control set, so it is not selected
from these exposed results. The candidate remains research-only.

An initial two-expert rule required both independently fitted templates to pass
their own separately calibrated linear and phase thresholds. The next
nonoverlapping Open Images validation-id block was downloaded without scoring;
2,000 candidates yielded 100 unique native 1024-by-1024 controls. The first
expert accepted none, the second accepted one, and their conjunction accepted
none. That rule appeared to add 5 detections across the 443 exact-1024 Google
files, including 2 of 95 July fixed-carrier misses.

A subsequent content-group audit invalidated those recall numbers. The 443
files contained three exact decoded-pixel duplicate pairs and ten
perceptual-hash groups at a conservative 16-of-256-bit screening distance. One
early near-duplicate pair had been split between the two expert fits, so the
experts were not content-independent. After allocating whole groups to one
side, selecting one representative per group, and recalibrating both experts
from the same untouched development controls produced templates correlated at
0.720, and the consensus retained only 6 of 443 Google files. It added 2 files
missed by the shipped carrier and retained only 1 of 95 July misses. It still
accepted no conjunction among 81 reserve exact-geometry
controls, 92 exact-1024 Open Images, 637 exact-1024 Picsum images, or the 100
new Open Images controls. The corrected result is specific but far too small
to ship.

Removing the exact-geometry restriction invalidated even that corrected
consensus. Across all 11,506 heterogeneous native controls, the group-separated
experts accepted 5 and 6 respectively, and their conjunction accepted 2. Both
consensus errors were at non-1024 geometries. The result is explicitly an
exact-1024 research candidate and does not supply a universal-size detector.

A post-hoc margin above both arbitrary-geometry collisions retained the two
corrected incremental exact-1024 positives. Applying that frozen margin to all
4,698 Google files accepted 28 and added 16 files missed by the shipped carrier
across 11 native geometries. A full-corpus perceptual audit assigned those 16
files to 16 separate content groups, none containing a shipped-carrier-positive
variant. The same margin accepted none of 1,500 Open Images, 637 unique Picsum,
or 12 Wikimedia native views. This is the first concrete all-size hypothesis
for the second direction, but the margin was selected after all 11,506
heterogeneous controls were exposed and the natural corpora had already
challenged related experts. It requires a new content-deduplicated AI-control
corpus before it can be treated as validation or runtime logic.

The next source-independent model-cohort challenge sharply bounded that
hypothesis. With no exact-byte overlap against the Spaces inventory, the
original group-separated conjunction accepted 2 of 589 public Gemini 3.1 Flash
Image Preview images, none of 520 Nano Banana Pro Preview, and none of 280
DALL-E 3 images. The two Gemini hits were visually distinct diverse images at
1408 by 768. Each Google cohort also included solid-color and gradient probes
over several native geometries. The post-hoc 1.033 strict margin rejected every
cohort image: Gemini reached 1.011, Nano Banana 0.941, and DALL-E 3 0.514. The
base rule therefore has weak transfer to a current Gemini cohort but still
collides with 2 of 11,506 arbitrary-size controls; the strict rule removes both
the controls and the current-Gemini transfer only through a post-test threshold.
Neither is a validated universal Google-model or cross-provider SynthID
detector. The 16 Spaces all-size hits and two public Gemini base hits are useful
hard positives for epoch analysis, not justification for implementation.

The near-duplicate audit also provided a small mechanistic diagnostic. In all
three perceptually matched pairs where only one variant crossed the shipped
carrier, subtracting the shipped variant from the non-shipped variant reduced
the shipped-template direction and increased both independently refitted
second-template directions. The normalized mean paired difference correlated
-0.568 with the shipped template and 0.252 and 0.264 with the two second
templates. Three pairs are insufficient for inference; the two-sided sign-test
result is 0.25. The paired result supports a carrier-state interpretation but
is not detector validation.

All three temporal detections from the original first-expert conjunction survived JPEG round trips
at qualities 95, 85, and 70. None survived WebP 95 or a 0.75x down-and-up resize
round trip. A symmetric transform challenge prevented promoting that positive
retention to a JPEG claim: one of 162 heterogeneous exact-1024 controls crossed
the unchanged rule after JPEG 85. The 92 exact-1024 Open Images and 637 unique
exact-1024 Picsum controls stayed below threshold in every view. The candidate
was native-only; fixed-lattice JPEG retention is diagnostic, not a certified
transport operating point. The transform result applies only to that
first-expert rule. The corrected group-separated experts have not been
transport-calibrated, so it supplies no robustness claim for them.

The corrected carrier was then tested causally. The normalized sum of the two
content-group-separated expert directions correlated 0.927 with each expert.
Subtracting it from all 16 strict incremental hits cleared every linear and
phase component on every image; the same amplitudes with a one-pixel cyclic
shift cleared none. Selected amplitudes were 5.0 through 7.75 integer levels,
with median 6.5. Fidelity ranged from 58.92 through 69.97 dB PSNR and 0.99961
through 0.99996 SSIM. The carrier itself was transform-fragile: only one of 16
sources remained strict after JPEG 95 or 90, and the aligned edit cleared that
one in both views while the shifted edit did not. No source remained strict
after JPEG 85, WebP 95, or a 0.75x resize round trip.

A joint ablation then started from all 28 strict second-carrier hits. It first
suppressed the shipped carrier to the frozen -0.25 target where required, then
suppressed the second direction until all four expert components were below
their base thresholds. The original cohort contained 12 first-carrier and 28
strict second-carrier detections; the aligned candidates contained zero of
either. The shifted controls left one first-carrier and seven strict
second-carrier detections. Median fidelity was 61.69 dB PSNR and 0.99984 SSIM;
the minima were 58.15 dB and 0.99910. The two edits did not reactivate one
another. Together with the failed third-carrier fit, the current linear native
16x16 hypothesis is locally exhausted as two jointly controllable states.
These are detector-score interventions, not Google-oracle removals.

### 2026-08-12: Registered color and phase-lock challenge

A crop-specific research branch tested whether the recovered 16x16 carrier is
better represented in a perceptual color space or a shift-tolerant directional
transform. Every branch reused the direct RGB period-and-phase registration,
fitted on the first 30 positives, selected on the next 20 positives and 200
controls, and reported the remaining 50 positives and 299 controls separately.
Only records whose recovered period was 15.5 through 16.5 were eligible.

The frozen RGB template's channel norms were `0.887:1.000:0.930` for R:G:B,
including `0.903:1.000:0.916` above FFT radius 4.5. An SVD assigned 79.80% of
template energy to a nearly equal-channel component, 18.39% to a
green-vs-magenta component, and 1.81% to a red-vs-blue component. The common
component had strong diagonal energy, while 98.6% of the coarse
green-opponent orientation energy was axis-aligned. This measured carrier does
not support a fixed `0.85:1.00:0.70` channel rule or an exclusively diagonal
decoder.

Nonlinear cube-root LMS coordinates from the OKLab transform exposed the
signal most strongly in the direct color-fold comparison, but the
development-selected full-vector candidate retained 32 of 50 final positives
and accepted six of 299 controls. This is evidence that nonlinear color
projections can improve carrier SNR, not evidence that the deployed embedder
uses Lab or OKLab internally.

A three-level DTCWT probe retained all six orientations rather than only the
`+/-45` degree pair. Its development-selected near-vertical green energy
candidate retained 37 of 50 final positives and accepted eight controls. The
green-opponent near-vertical candidate retained 39 positives and accepted one
control. Separating energy, normalized complex correlation, and phase-only
coherence changed the development choice to all-orientation green-opponent
phase coherence, which retained 37 positives and accepted four controls. The
directional representation therefore exposes real carrier structure but fails
the low-false-positive gate.

An explicit FFT probe then froze 8, 16, 32, or 64 carrier bins from the fit
positives and compared signed cosine phase coherence with the proposed
`abs(cos(delta_phase)) > 0.90` rule. The absolute rule never produced a usable
operating point; treating phase and antiphase as equivalent increased the null
overlap. With 64 bins, the development-selected green-channel signed cosine
retained 26 of 50 final positives and initially accepted none of 299 controls.
That result was underpowered because only 39 of 499 controls selected the
eligible period-16 branch.

The green phase candidate and its threshold were frozen before a full
period-and-phase search over 1,000 COCO controls. It accepted five controls.
Among the 129 eligible controls, the maximum score was `0.6910271977636098`,
above the frozen `0.5443545641095117` threshold. Raising the threshold above
that maximum retained only eight of 100 positives. Explicit registered phase
lock is therefore a useful diagnostic of this carrier family but is rejected
as a standalone detector. Because it shares the RGB registration stage, it is
also not independent confirmation of the carrier.

### 2026-08-12: Green phase perturbation and blind SWT removal

A second removal probe tested the specific claim that changing only phase at
the recovered Green-channel carrier bins can preserve spectral magnitude and
image fidelity while defeating detection. It used the 100-image public Gemini
set at native period 16 and modified conjugate FFT pairs together so the
inverse remained real. Before pixel quantization, the maximum absolute change
in FFT magnitude was `5.24e-10` for the 32-pair inversion. After clipping and
rounding to 8-bit pixels, the maximum magnitude change relative to the largest
source coefficient was 0.175%.

The native periodic detector accepted 59 of the 100 sources. Inverting the 32
strongest unique Green-channel carrier pairs left one of those 59 positive.
Across all 100 images, PSNR was at least 43.36 dB and SSIM at least 0.99048;
the medians were 52.79 dB and 0.99739. Median signed phase coherence moved from
0.485 to -0.371 and the median full RGB tile score moved from 0.230 to 0.041.
This reproduces the proposed fidelity and local-score effect against the
recovered periodic detector.

It does not establish SynthID removal. The current test targets the same
carrier used by the local score, and earlier wider complex-spectrum and
phase-projection candidates already cleared local phase models at 51.94-56.03
dB while remaining detected in healthy Google verifier sessions. The 32-pair
Green candidate is therefore a preregistered oracle candidate, not a remover.
The official SynthID-Image description also identifies a post-hoc neural,
content-dependent encoder-decoder rather than a fixed Fourier codebook; it
does not document phase bins as its decision surface.

The preregistered Google-oracle challenge then used three of the strongest
local positives. Each fixed group contained the original, its 32-pair Green
phase inversion, and an RMS-matched random-noise sham. All three phase
candidates fell below the local `0.17357069773071196` threshold, with PSNR
from 55.41 to 57.86 dB and SSIM from 0.99709 to 0.99807. The three shams
remained locally positive. Nine files were submitted to Gemini's `Verify with
SynthID` tool in separate chats with the unchanged prompt. Eight verdicts
persisted and all eight reported Google AI signals. This includes all three
phase candidates, both recoverable source controls, and all three shams. The
second source request was submitted, but its chat did not persist and no
verdict could be recovered; it was not retried outside the fixed upload budget.

This falsifies the operative removal claim: Green-carrier phase inversion
clears the local periodic correlate on three of three images but clears the
Google oracle on zero of three. It is evidence that the local template observes
one stable component or correlate of SynthID, not that these FFT coefficients
form the proprietary decoder's sufficient decision surface. Do not productize
the Green phase inversion or report its local score change as SynthID removal.

The three oracle-confirmed phase candidates were then treated as adversarial
hard positives for detector analysis, without using them to relax the existing
runtime thresholds. Both runtime modes missed all three. Their native scores
were 0.126-0.160 against the 0.174 threshold; their registered decision scores
were 0, 0, and 0.553 against the threshold of 1. A phase-invariant magnitude
profile was therefore tested as a possible rescue. The development-selected
all-bin RGB profile retained 39 of 50 final positives but accepted one of 299
final Open Images controls and still missed all three hard positives.

A frozen-template, top-32 Blue-magnitude profile did accept all three hard
positives and initially accepted none of 499 Open Images controls, but this was
a post-hoc hard-positive-selected branch with low ordinary sensitivity: 17 of
70 development and final positives. Its frozen threshold accepted 39 of 1,000
fresh COCO controls. Combining it with a native-score floor of 0.10 happened to
accept none of all 3,000 COCO controls while retaining the three hard positives,
but failed the next independent challenge: 90 of 11,506 metadata-labeled
non-Google controls passed both gates. Accepted controls included Adobe
Firefly, local diffusion, Samsung, Microsoft, and several other generator
families. The phase-invariant magnitude rescue is therefore rejected as a
provider-specific detector; it measures a shared periodic rendering family.

Channel separation exposed a narrower attack-specific rescue. The Green-only
phase inversion leaves Red and Blue pixels unchanged, but the runtime RGB score
normalizes all three channels jointly. On the three oracle-confirmed hard
positives, separate signed correlations remained 0.781-0.804 in Red and
0.798-0.825 in Blue while Green moved to -0.400 through -0.645. A Red threshold
of `0.3770237083693908`, frozen above 200 Open Images calibration controls,
retained 16 of 70 development and final ordinary positives and accepted none
of the remaining 299 Open Images controls. It also accepted all three oracle
hard positives and none of 3,000 fresh COCO controls.

Red correlation alone remained a generic periodic-renderer correlate: it
accepted 96 of 11,506 metadata-labeled non-Google controls. Every one of those
96 had positive Green correlation. The attack-specific conjunction of Red at
or above the frozen threshold and negative Green accepted none of 15,005 total
controls across three independent corpora, while retaining all three
oracle-confirmed phase candidates. Across the 100-image synthetic inversion
probe, it recovered 19 of the 58 locally detected sources that the attack had
moved below the RGB threshold. One additional attacked image still passed the
existing detector.

This channel-discordance rule is the first zero-control rescue for the
oracle-confirmed hard positives, but it is not added to runtime. Its form was
motivated after inspecting the attack, only three examples carry external
oracle labels, and its synthetic rescue sensitivity is 19 of 58.

A follow-up challenge registered that frozen rule over all 256 modulo-16 phase
offsets and six fixed carrier periods: 8, 10.4, 12, 16, 20, and 24 pixels. The
Red-only form accepted one of 3,000 COCO controls during phase registration;
period search added no further acceptance. The accepted control scored 0.395
in Red but only 0.267 in Blue. This rejects Red-only registered rescue at the
existing threshold.

The previously frozen `min(Red, Blue) >= 0.3770237083693908` candidate, still
combined with negative Green, accepted none of the same 3,000 controls under
phase-only or phase-and-period registration. Its maximum registered control
score was 0.342. A symmetric transform stress test then evaluated all twelve
identity, crop, JPEG, and resize views for 100 fixed Open Images controls. None
of the 1,200 inputs was accepted; the maximum was 0.332.

The stricter rule retained all three oracle-confirmed hard positives at native
scale and after offsets of 1x1 and 7x11 pixels or a centered 5% crop. Period
registration retained all three after 0.65x, 0.75x, 1.25x, and 1.5x resizing.
It retained none after 0.5x resizing or JPEG round trips at qualities 95, 85,
and 70. Every source and RMS-noise sham remained negative in all twelve views.
The small-control zero was not sufficient for the complete period bank. A
later five-period search over all 11,506 metadata-labeled non-Google controls
accepted 16 at the original 0.377 threshold: two at period 20 and 14 at period
24. The maximum `min(Red, Blue)` score was 0.435813. This rejects one common
threshold across periods 10.4 through 24.

A conservative high-score branch was then frozen strictly above that measured
maximum. It retained all three hard positives at periods 12, 16, 20, and 24,
corresponding to 0.75x through 1.5x resizing, identity, and the three crop
views. A symmetric full-corpus resize challenge accepted none of 11,506
controls at 0.75x, 1.25x, or 1.5x; the respective maxima were 0.431352,
0.393949, and 0.372036. The 0.65x path needed separate treatment. Its native
period-10.4 null maximum was 0.361367, below all three hard positives, but a
symmetric 0.65x resize round trip raised one control to 0.397396, above the
weakest hard positive at 0.394911.

That collision motivated an exploratory low-period channel-ratio gate:
`min(Red, Blue) >= 0.3770237083693908`, negative Green, and
`Blue >= 1.1 * Red`, only at period 10.4. It retained all three 0.65x hard
positives. Among all 11,506 controls, the largest score satisfying the ratio
gate was 0.355165 natively and 0.354955 after the symmetric 0.65x round trip,
so neither challenge accepted a control. The combined exploratory rule also
retained all three hard positives in the identity, three crop, 0.65x, 0.75x,
1.25x, and 1.5x views, while every corresponding source and RMS-noise sham
remained negative.

Applying the combined rule without further tuning to the 100-image synthetic
Green-inversion cohort exposed its low sensitivity. Among the 58 attacks that
moved a natively detected source below the native detector threshold, the rule
recovered 4 at 0.65x, 5 at 0.75x, 16 at identity, 11 at 1.25x, and 10 at 1.5x.
The three oracle source images are members of that cohort; only one additional
synthetic source passed the 0.65x branch. The rule is therefore a
high-specificity rescue for a strong residual R/B carrier, not a general
solution to Green-phase perturbation.

A source-split Fisher projection then tested whether a learned three-channel
direction could improve that sensitivity. Red, Green, and Blue correlations
were standardized separately by scale, and the projection was fitted from 34
training attacks and 5,719 training controls. Per-scale thresholds were frozen
above every training-control score. They accepted 11 of 23,148 views from the
5,787 test controls. On the seven source-held-out attacks, the projection
recovered 0 at 0.65x, 0 at 0.75x, 2 at 1.25x, and 2 at 1.5x. It is both less
specific and less sensitive than the explicit rule and is rejected.

Spatial consistency at 0.65x was also insufficient. At the globally selected
period-10.4 phase, a 2x2 and 4x4 aligned grid measured local R/B strength,
negative-G coverage, and `Blue / Red` coverage on all 537 controls in the
global-score tail at or above 0.20 and on all 58 synthetic native-detector
misses. Every individual feature overlapped the control tail. Within a small
fixed grid of global floors and integer coverage counts, the best zero-control
conjunction recovered four attacks, no more than the simpler global ratio
rule. Lowering the global floor to 0.30 recovered five but accepted two
controls. The spatial branch is rejected as non-improving.

This establishes bounded transform behavior for the attack diagnostic, not a
universal detector. The 0.65x ratio was selected after seeing the full-corpus
collision, the conservative threshold was derived from an exposed control
corpus, the period bank is discrete, only three recovered images have oracle
labels, and JPEG sensitivity is zero in this probe. The next valid gate remains
new oracle-confirmed Green-perturbed positives plus a preregistered untouched
control corpus. The branch stays outside runtime until that gate passes.

An exploratory channel-contrast extension then tested whether the magnitude of
the negative Green response could recover the failed JPEG and 0.5x views. The
metrics were fixed as `min(Red, Blue) - Green` and
`mean(Red, Blue) - Green`; 50 Open Images controls across all twelve transforms
set thresholds before the remaining 50 controls were scored. Calibration over
600 views required thresholds of 0.655 and 0.695. Neither metric accepted an
evaluation control, but both still recovered zero of three JPEG cases at every
quality and only one of three 0.5x cases. A relaxed R/B-only threshold produced
the same result. Negative-G magnitude therefore adds no useful transform
coverage at the measured low-false-positive boundary and is rejected.

Codec-specific templates were then fitted from 50 other public positives after
JPEG 95, 85, and 70 round trips, excluding all three oracle hard-positive
sources. Neither a quality-matched template nor a three-quality bank recovered
any of the nine JPEG hard-positive views. They accepted respectively three and
two of 150 evaluation-control views. The templates primarily captured the JPEG
8x8 grid and were rejected.

Filtering the unchanged 16x16 template to radial frequency 0.5 through 4.5
exposed a real JPEG-surviving component. At a threshold above the first 300
Open Images JPEG views it retained all three hard positives at qualities 95,
85, and 70. The next frozen challenge rejected it: phase search accepted 35
native, 50 JPEG-95, 48 JPEG-85, and 46 JPEG-70 views among 3,000 COCO images.
Cross-band phase agreement did not separate the nine hard-positive views from
those 179 false positives.

A spatial gate required negative Green in all four quadrants and a median
quadrant R/B score above the COCO false-positive maximum. It retained all three
hard positives at JPEG 95 and 85 but none at JPEG 70. On 11,506
metadata-labeled non-Google controls it nevertheless accepted 35 native, 66
JPEG-95, and 88 JPEG-85 views. The errors included genuine camera images and
multiple unrelated generators. Scoring only the unchanged phase also failed,
accepting 38 native and 210 JPEG views among 3,000 COCO images; its maximum
control score of 0.673 exceeded the 0.464-0.609 hard-positive range. The
JPEG-stable band is a general low-frequency or codec lattice, not a
SynthID-specific rescue, and all of these branches are rejected.

The 0.5x boundary was challenged separately with a physically reduced 8x8
template. Projecting the dominant 2x2 lattice out of both observation and
template before scoring R/B with negative Green removed the known nuisance but
not the overlap. Across all 11,506 symmetrically downscaled controls, the
zero-control threshold was 0.396. The three oracle hard positives scored only
0.277-0.288. Channel separation therefore cannot rescue the rejected period-8
branch.

An untouched 2026-08-07 through 2026-08-10 temporal cohort then challenged the
runtime template and thresholds. Cohorts were recomputed from explicit
provenance because a provider-only split incorrectly placed mixed Google/OpenAI
lineage in the negative set. The frozen native detector accepted 183 of 252
files with explicit Google LLC SynthID provenance and 3 of 488 with explicit
OpenAI-only SynthID provenance. Scale registration accepted 130 and 1,
respectively. Among 170 files with no SynthID provenance assertion, native and
registered modes accepted eight and two. These operational errors are not
provider-oracle negatives and cannot establish the true false-positive rate.

The native detector remained positive on 153 of 252 explicit-Google images
after a symmetric 0.75x resize round trip, 66 after JPEG-95, and 54 after
WebP-95. A 5% center-crop round trip retained none. This fresh temporal result
confirms a real, partly codec-tolerant Google pixel signal across many stored
sizes, while rejecting the stronger claim that the fixed-phase runtime score
is a universal SynthID decoder. The post-hoc strict second carrier did not
generalize: it accepted only 2 of 234 Google-platform positives and none of 689
provider-split controls. Applying the already frozen scale-registration path
after the crop recovered only 8 of 252 explicit-Google files and accepted none
of 488 explicit OpenAI-only files. The existing scale search does not solve the
crop phase boundary.

A diagnostic joint-scale-and-phase probe then reversed the known 0.95 crop
scale and scored the carrier at the cyclic phase predicted from the removed
border. It reached 0.859 AUC for explicit Google provenance against all other
temporal cohorts. A post-hoc threshold above all 671 other rows retained 37 of
252 explicit-Google rows. Exhaustively searching all 256 tile phases was weaker
at 0.839 AUC and retained 41 rows above its own zero-control threshold. The
fixed geometric phase supplies a plausible crop mechanism and a candidate for
the next preregistered temporal challenge, not a calibrated runtime mode: both
the transform and reported operating point have now observed this cohort.

A blind three-level `db2` SWT probe then soft-thresholded only the Green
horizontal, vertical, or diagonal detail bands at 0.25, 0.5, 1, and 2 times the
band's robust noise estimate. Diagonal HH thresholding left all 59 original
positives detected at every strength. Vertical thresholding cleared four at
strength 1 and five at strength 2, but the respective minimum fidelity fell to
32.57 dB and 0.96971 SSIM, then 28.52 dB and 0.93646. At strength 1, vertical
score reduction exceeded diagonal reduction on 97 of 100 paired images
(`p = 2.63e-25`, exact two-sided sign test). Blind HH soft-thresholding is
therefore rejected; the stronger vertical response is consistent with the
separately measured axis-aligned green-opponent carrier component.

### 2026-08-13: patent architecture and amplitude confound audit

The official paper intentionally leaves the neural network architecture
unspecified, but a related DeepMind patent family with overlapping authors gives
more specific architectural evidence. Its image example constructs a
content-dependent residual as `x' = x + g(x)`, describes a U-Net-like encoder
and convolutional decoder, injects a message or secret into intermediate layers,
and trains clean and watermarked pairs under the same sampled transformations.
It also permits a bank of paired networks in which one decoder is deliberately
unable to recognize another pair's mark. These patent alternatives are not
proof of the exact production implementation, but they invalidate the working
assumption that SynthID must reduce to one provider-independent, fixed
spread-spectrum key. Multiple Google states and a distinct OpenAI carrier are
compatible with one technology family.

This changes the role of the shipped 16-by-16 template. It is a validated linear
expert for one observable encoder state, not a surrogate for the official
nonlinear detection logit. A universal local detector should be designed as a
versioned union of independently calibrated experts, with family-wise
false-positive control and an explicit abstention region. New experts still
need source-matched clean counterfactuals or provider-oracle labels; metadata
absence is not a negative label.

A symmetric transform-stability experiment challenged a simpler rescue. The
weak oracle-positive `07.png` scored 0.1248 natively, 0.0288 after JPEG 95,
-0.0023 after JPEG 85, 0.1179 after a 0.99x Lanczos round trip, and 0.0791 after
an eight-pixel crop round trip. The oracle-negative Open Images chestnut scored
0.2124, 0.1322, 0.0482, 0.2274, and 0.0601 under the same views. Both signals
degrade similarly under codec and crop operations. Multi-view stability does
not distinguish the weak positive from this natural lattice confound and is
rejected as a rescue gate.

Raw folded-tile amplitude was also tested because `07.png` had a norm of 6.924,
compared with 3.017 for the chestnut and 0.874 for the strongest tested resized
Kodak confound. The full corpus rejects a general amplitude gate. Among 4,698
Google rows, the current score threshold accepts 3,928, but accepted norms run
as low as 0.712. A post-hoc branch at `score >= 0.121` and `norm >= 5` would add
190 rows below the current threshold, yet an observed-geometry development
control already reaches score 0.120911 at norm 15.339. The margin to `07.png`
is under 0.004 and there is no untouched validation set. Amplitude is useful as
a support diagnostic, but neither a veto nor this low-score rescue is eligible
for runtime.

The next defensible Google experiment is consequently a preregistered
multi-expert cascade: preserve the current carrier unchanged; train candidate
experts only on source-grouped paired or oracle-labeled data; calibrate every
expert and their union on untouched natural, resize, codec, and provider
controls; and return `unknown` when neither the watermarked nor unwatermarked
hypothesis clears its calibrated boundary.

The newly published MarkNull work supplies an independent no-box removal
baseline. It reports 100% attack success on 20 Imagen-3 images checked through
Gemini's verification flow. The attack uses a clean Stable Diffusion proxy to
invert each image, optimize a bounded latent against a noise-latent alignment
loss plus LPIPS, MSE, and SSIM, and decode it again. Its milder SynthID setting
still reports only 25.36 dB PSNR and 0.80 SSIM. It therefore strengthens the
case for latent regeneration as a detector-independent fallback, but it does
not meet this project's pixel-only or fidelity gates.

The associated [public repository](https://github.com/JieJayCao/MarkNull)
contributed 50 metadata-free 512-by-512 Gemini/Imagen source candidates, but no
attacked SynthID pairs in the inspected Git tree. The paper reports only 20
oracle-evaluated sources and does not map those verdicts to filenames, so all 50
remain source-asserted candidates rather than individual oracle labels. Both
shipped experts detected zero of 50. More precisely, the fixed runtime expert
reported unsupported because 512 by 512 is below its calibrated pixel-count
floor. Its raw diagnostic score ranged from -0.1044 to 0.1058. Scale
registration supported all 50 and accepted none, with its highest decision
statistic at 0.9574 below the frozen 1.0 threshold. The shared scorer in
`scripts/synthid_runtime_expert_scores.py` now records this distinction and
exports both observations from one pixel decode.

An external-source split nevertheless exposed a highly reproducible period-4
component. Templates from the first and second 25 images correlated at 0.958.
A template fitted only on the first half accepted 22 of 25 held-out candidates
at a threshold above 250 canonicalized COCO development controls and accepted
zero of a separate 250 COCO controls. The broader challenge rejected watermark
specificity: it accepted two of 300 heterogeneous AI controls and five of 282
content-deduplicated internal negative-test controls at the same frozen
threshold.

The mechanism diagnostics also identify the confound. The period-4 mean placed
82.4% of its non-DC spectral power in the horizontal Nyquist bin, and stable
correlations at larger even periods vanished after projecting out all period-4
harmonics. Its strongest channel was Blue rather than Green, and its best
phase-aware correlation with a fourfold-reduced shipped carrier was only 0.375.
This is an axial renderer or resampling signature, not evidence for another
validated diagonal SynthID carrier. It is retained as a hard-negative feature
and excluded from the runtime expert bank.

A schema-versioned conformal cascade now implements the required aggregation in
`scripts/synthid_conformal_cascade.py`. Every configured expert must emit an
explicit supported score or unsupported result. For presence, the smallest
empirical clean-null upper-tail p-value receives a Bonferroni correction over
the supported expert bank. For absence, the largest lower-tail p-value against
each expert's positive calibration is used, so every possible encoder state
must be rejected. `not_detected` is disabled unless the calibration manifest
explicitly declares complete version coverage and every expert supports the
query. Input and output manifests are hash-pinned for reproducibility.

The first source-disjoint smoke test used only the unchanged fixed 16-by-16
expert. Alternating content hashes supplied 2,347 source-asserted Google
calibration rows and 2,346 evaluation rows. The existing observed-geometry COCO
partitions supplied 3,000 development controls and 2,000 final controls. At a
two-sided alpha of 0.001 with incomplete-version coverage, the cascade detected
2,084 of 2,346 Google rows and one of 2,000 final natural controls; all other
rows abstained and none returned `not_detected`. The corresponding frozen
runtime threshold detected 1,954 Google rows and zero final controls. The
conformal point therefore recovers 130 additional source-asserted positives at
the cost of one natural false positive. It is statistically compatible with
the target 0.1% FPR, but it is not a runtime replacement: the corpus has already
influenced detector development, Google labels are provenance assertions rather
than per-file oracle verdicts, and a multi-expert union still needs a fresh
family-wise challenge.

The fixed and scale-registered experts were then evaluated together on their
frozen source-disjoint resize challenge. Current production scores were
recomputed from pixels for all 355 transformed Google candidates and 499
untouched Open Images controls. Sorting each label by source identifier and
alternating rows produced 178 positive and 250 negative registered-calibration
examples, followed by 177 positive and 249 negative evaluation examples. The
fixed calibration used 4,516 Google sources after excluding every evaluation
source and 2,980 observed-geometry development controls. At the unchanged
runtime thresholds, fixed accepted 8 evaluation positives, registered accepted
116, and their union accepted 117 of 177 with zero of 249 controls. On the full
descriptive corpus the corresponding counts were 15, 229, and 231 of 355, again
with zero of 499 controls. Registered scale search therefore supplies 109
source-disjoint evaluation positives that the fixed expert misses; the fixed
expert adds one that registered misses.

Applying the empirical cascade at alpha 0.01 was less specific. It accepted 122
of 177 evaluation positives but also five of 249 controls. All five control hits
came from the registered branch below its frozen decision threshold. The
250-control calibration provides only 0.00398 p-value granularity, and lowering
the operating point merely traded five additional positives for five false
positives. This conformal operating point is rejected. The implementation is
retained as versioned calibration infrastructure, while the independently
frozen production thresholds remain the valid two-expert decisions.

A wider calibration reused the already saved component reports for 11,273
supported, symmetrically resized Spaces controls. The stored high-band value
made the current registered decision score exactly reconstructible throughout
the relevant upper tail; rows screened below the historical 0.1182 amplitude
ratio cannot affect this tail. At alpha 0.001, the two-expert cascade accepted
119 of 177 evaluation positives and zero of 249 controls. The two additions
over the runtime union had registered scores 0.9830 and 0.9731, with corrected
clean-null p-values of 0.000710. This initially appeared to be a non-failing
multi-expert calibration point, but the positive challenge had already been
exposed. The alpha, expert bank, and thresholds were frozen before the fresh
test below.

The decisive reserve used the next 1,500 sorted Open Images validation IDs,
3,500 through 4,999, frozen before scoring. Download and geometry checks yielded
1,000 registered-supported controls with no decoded-pixel hash overlap against
the prior 1,499 Open Images controls. Registered scale search accepted zero.
The fixed runtime threshold accepted 7 of the 81 controls in its supported
geometry, or 7 of 1,000 overall, so a simple OR of the two experts also accepted
seven. The frozen alpha-0.001 cascade was worse: it accepted nine controls,
eight through the fixed tail and one registered-only row at score 0.8690.
The candidate is rejected. In overlapping geometry, fixed-only evidence cannot
be added to registered evidence without a new specificity mechanism; keeping
the fixed detector available as a separately scoped diagnostic does not make
their union safe.

The fixed-only geometry does not provide a fallback. Among 89 saved non-Google
Spaces controls from 10 to 18 megapixels, where registered mode is unsupported
but fixed mode is supported, 10 crossed the fixed threshold. The errors span
multiple generator families. A geometry router therefore cannot extend recall
by selecting fixed whenever registered is unavailable.

`scripts/synthid_routed_expert_bank.py` implements the surviving conservative
policy without changing the standalone detectors. When registered mode is
supported, only its frozen threshold can produce `detected`; a fixed-only
crossing is retained in the report as `fixed_only_ambiguous`. When registered
mode is unsupported, fixed evidence is likewise reported but the bank abstains.
The bank never returns absence because encoder-version coverage is incomplete.
On all 355 transformed positives and 499 reserve controls it detected 229 and
zero. On the fresh 1,000-image reserve it detected zero and explicitly routed
the seven fixed crossings to abstention. This is a safe expert-bank baseline,
not a universal SynthID decoder: scale 0.5, unmeasured encoder states, and the
separate OpenAI family still require additional validated experts.

Directly enlarging registered mode's pixel ceiling also failed. The unchanged
registered components were computed on every saved 10-to-18-megapixel example:
37 Google candidates and 89 non-Google Spaces controls. The frozen threshold
accepted one positive and zero controls. Amplitude passed for 28 positives and
the selected spatial and spectral periods agreed for 21, but only three cleared
the high-band gate. Large full-frame spectra therefore lose almost all recall;
the absence of control errors does not justify widening the declared geometry.
Phase-aligned window aggregation inside the calibrated range is the next
bounded large-image hypothesis. That hypothesis was then challenged with every
phase-aligned 2,048-square window. Median-window scoring retained 36 of 37
positives but also 10 of 89 controls; requiring every window to pass retained
36 positives and eight controls. The false lattices are spatially coherent, so
window consensus cannot validate a large-image fixed fallback. Large images
outside registered scope remain abstentions.

A final frozen full-frame alternative isotropically reduced each large image to
eight megapixels with area interpolation before applying the unchanged
registered detector. This maps a native period 16 into approximately 10.7-14.3
pixels, inside the calibrated period range, without discarding spatial regions.
It still accepted only 1 of 37 positives and zero of 89 controls, and the one
hit was the same 4096-square image detected natively. Amplitude passed for 26
positives, period agreement for 16, and high-band agreement for only three.
Pre-resizing therefore does not recover the missing evidence and adds harmonic
ambiguity; no target-size sweep is justified on this exposed cohort.

The scale-0.5 failure was also rechecked without the registered detector's
sequential amplitude gate. High-band correlation was computed for all 65
period-8 positives and all 499 reserve controls. Positive and control medians
were 0.0184 and 0.0213, with ranges -0.2381 to 0.1930 and -0.1734 to 0.2148.
Normalized amplitude also overlapped: positive median and maximum were 0.4611
and 0.9259, compared with 0.3824 and 1.6296 for controls. Requiring amplitude
and high-band evidence jointly therefore cannot recover this scale at the
frozen specificity. The 0.5x case remains an explicit blind spot rather than an
eligible lower-threshold branch.

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

### 2026-08-12: OpenAI opponent-color carrier challenge

The RGB periodic and learned branches did not test the hypothesis that a weak
carrier is clearer after the nonlinear LMS transform used by OKLab. A new
validation-only screen compared sRGB, linear RGB, cube-root LMS, OKLab, and an
orthonormal linear opponent basis. For each representation it tested periods
4, 8, and 16 plus whole-vector, single-channel, and chroma-vector folds. Every
candidate fitted a positive-minus-control direction independently in the native
and JPEG-95 views. A positive had to cross both thresholds, with each threshold
strictly above every validation control in the corresponding view.

The development corpus was limited to the three OpenAI native geometries:
1024x1024, 1024x1536, and 1536x1024. It contained 283/140/158 OpenAI
train/validation/test images and 252/145/135 heterogeneous controls. The best
validation candidate was the third cube-root LMS component at period 8. It
accepted 19 of 140 validation positives. The frozen locked test accepted 16 of
158 positives and none of 135 controls in the conjunctive native-plus-JPEG
rule. Native alone accepted 43 positives and one control; JPEG-95 alone accepted
22 positives and a different control. The native and JPEG templates correlated
at 0.890.

The 16 test hits were not a single date, geometry, or content family. They
spanned 11 collection dates; the 1024x1024, 1024x1536, and 1536x1024 cohorts
contributed 2, 8, and 6 hits. A 256-bit DCT-hash audit found two multi-member
perceptual groups in the complete 581-image OpenAI native cohort, but neither
connected an accepted test image to another split. Thresholding against the
union of heterogeneous validation controls and 140 matched 0.75x-down-and-up
OpenAI views did not change the operating point. The 158 matched test views
accepted none while their 16 corresponding source views remained accepted.

The transform boundary is mixed. All 16 source hits remained conjunctively
accepted after WebP-95; the complete test set then contained 26 accepted OpenAI
images and one accepted control. JPEG-90 retained four of the 16. Crop and 0.75x
resize round trips retained none. Searching all 64 cyclic period-8 phases did
not restore geometric robustness: resize retained 2 of 158 positives and one
of 135 controls, while crop retained no positive and one control. The loss is
not merely an unknown modulo origin.

The candidate was also scored without refitting on all 52 action-derived
same-provider controls at these geometries. It accepted one of 52 and none of
the 12 controls explicitly naming `gpt-image 2.0`. The exact-version subset is
only 8/2/2 train/validation/test by the native geometry restriction, and the
absence of `c2pa.watermarked.unbound` remains an action-derived candidate label,
not a provider-oracle negative. These counts cannot establish an OpenAI-specific
false-positive rate.

The dominant exporter lattice was removed explicitly. The raw period-8
template placed 84-90% of its energy in period-2 or period-4 subspaces. For
each image, projecting out the complete period-4 component before refitting
reduced native/JPEG template correlation to 0.564 but still accepted 18 of 140
validation and 15 of 158 test positives with zero test controls. The useful
residual therefore does not collapse to the previously documented 2x2/4x4
generator lattice.

A direct pixel ablation tested causality against the frozen local score. The
normalized native period-8 direction was subtracted only from the sRGB Blue
channel, with a scalar search for the smallest amplitude that cleared both the
native and JPEG-95 thresholds. All 16 locked-test sources cleared. Repeating
the same selected amplitude at the least-correlated cyclic phase cleared none
of 16. Median amplitude was two Blue-channel integer levels, median PSNR was
52.24 dB, and median SSIM was 0.99639. The minima were 40.62 dB and 0.97184,
so even as a local ablation this is not yet a production-quality remover.
More importantly, score causality does not establish that the candidate is the
OpenAI SynthID decoder surface.

An all-size map then evaluated the same fixed native period through partial
modulo folds, so dimensions did not need to be divisible by eight. It accepted
94 of all 7,259 OpenAI-labeled files across 13 of 605 geometries and 9 of 8,670
heterogeneous controls across 7 of 1,534 geometries. The three fit geometries
contributed 76 positives. The largest exported geometries, including 2,265
files at 1086x1448 and 992 at 1254x1254, contributed none. Two corpus rows were
excluded because their decoded geometry no longer matched the indexed metadata.

A scale search was frozen to integer periods 4 through 16 before examining the
all-size results. Its score was the maximum, across periods, of the minimum
native and JPEG-95 correlations. The common threshold was set above every
period-searched validation control, thereby charging the search itself against
specificity. It accepted 13 of 1,854 validation positives and none of 2,227
validation controls. On test it accepted 14 of 1,839 positives and one of 2,162
controls. Every accepted OpenAI image selected period 8; no other period added
a hit. The carrier does not scale continuously with stored resolution.

This is the strongest local OpenAI periodic candidate so far: it is codec
tolerant, survives explicit subperiod deflation, has a phase-specific causal
ablation, and is not explained by date, native geometry, or hash-group leakage.
It is still research-only. It has low sensitivity, fails geometric transforms,
has one all-size test-control collision, and lacks a matching-provider oracle.
The next independent branch should look for a resampling-invariant,
content-dependent residual on source-grouped data rather than broadening the
same period search. No runtime OpenAI pixel expert or remover is justified.

The next branch removed phase from the folded LMS spectrum and required three
views: native pixels, JPEG 95, and a 0.75x down-and-up resize. It screened
magnitude, power, and log-magnitude profiles at periods 4 through 16 on
validation only. The selected period-16 power candidate used a separately
fitted template for each view. It accepted 8 of 140 validation positives and 8
of 158 locked-test positives, with no native-geometry control accepted in
either split. On the complete wide challenge it accepted none of 2,227
validation and 2,162 test Spaces controls, one of all 261 action-derived
same-provider controls, and none of the 118 exact-version `gpt-image 2.0`
controls. Five of its eight test hits overlapped the signed period-8 candidate;
three were additional.

Subperiod deflation bounded that result. Removing the exact period-8 Fourier
support from each period-16 spectrum improved native-to-resize template
correlation from 0.061 to 0.925, but the locked test then retained five
positives and accepted two of 135 controls. Removing period-4 support retained
no test positive. The transform-tolerant energy is therefore part of the same
harmonic family rather than a clearly independent carrier.

Finally, a stricter experiment required one shared phase-free template across
all three views. Validation selected period-15 magnitude, whose independently
measured view directions correlated 0.992 for native versus JPEG and 0.900 for
native versus resize. It retained 7 of 158 native-geometry locked-test
positives and none of 135 controls. That apparent invariance failed on the
wide geometry challenge: the same thresholds accepted 11 of 2,227 validation
and 14 of 2,162 test Spaces controls, plus seven of 261 same-provider controls
and two of 118 exact-version controls. It is a general renderer or resampling
spectrum and is rejected.

The separately fitted period-16 three-view ensemble remains a useful research
diagnostic because it survived the broader control challenge, but it is not a
single codebook, has only eight native-geometry test positives, and derives
most of its signal from the same subperiod family. It does not rescue the
universal-detector claim or justify runtime code.

A non-learned fractal hypothesis was tested last. For each image it compared
the phase-free cube-root LMS spectrum with the same image after JPEG 95 and
after a physical 0.75x reduction. Candidate native periods 8, 12, 16, 20, and
24 were paired with scaled periods 6, 9, 12, 15, and 18. The score was the
minimum of native-to-JPEG and native-to-scaled spectral cosine, so no provider
template or fixed phase participated. Validation selected period 12-to-9
log-magnitude and retained 3 of 140 positives above all 145 controls. The
locked test accepted none of 158 OpenAI positives and one of 135 controls; the
OpenAI median was 0.515 versus 0.555 for controls. Simple phase-free spectral
self-similarity is not an OpenAI watermark feature and the fractal branch is
rejected.

The scale hypothesis was then challenged against the common non-native export
geometries. A nearest-native inverse-raster surrogate recovered none of 1,321
test OpenAI images and accepted two of 1,485 symmetrically resampled control
views. That mapping was intentionally treated as incomplete because it changed
aspect ratio for important cohorts. The largest cohort, 1086x1448, is instead
consistent with an isotropic `1/sqrt(2)` reduction from 1536x2048. Restoring
that exact hypothesized source raster still recovered none of 579 validation
or 562 test positives. A direct fractional-phase fold avoided inverse
interpolation and searched two raster-coordinate conventions plus all 64 cyclic
origins, charging the complete registration search against validation
controls. It retained 2 of 579 validation and 4 of 562 test positives while
accepting 2 of 135 test controls. Its median score was lower for OpenAI than
for controls. The fractional-carrier explanation for this dominant export
geometry is rejected.

A nonlinear cyclostationary screen next tested whether content-dependent or
payload-varying signs cancel the cross-image mean while leaving a periodic
variance. It compared folded magnitude, energy, locally normalized energy,
and cross-channel products in cube-root LMS and OKLab. Validation selected the
absolute residual of the third cube-root LMS component at period 4. It retained
33 of 140 validation and 43 of 158 locked-test positives, but also accepted 2
of 135 locked-test controls. The frozen wide challenge confirmed a renderer
confound: it accepted 48 of 1,854 validation and 52 of 1,839 test OpenAI images,
against 7 of 2,227 validation and 5 of 2,162 test Spaces controls. It also
accepted 10 of 261 action-derived same-provider controls, including 5 of 118
that explicitly name `gpt-image 2.0`. Requiring spatial agreement did not
repair specificity; the validation-selected median over four quadrants kept
41 of 158 test positives and the same two native-geometry test controls.

Finally, a second-order cyclic screen folded spatial products of the residual
with lags 1, 2, 4, and 8 along axial and diagonal directions. It evaluated 360
fixed LMS/OKLab, channel, period, lag, and normalization combinations. The
validation winner used the second cube-root LMS component, period 16, and a
vertical four-pixel lag. It retained 36 of 140 validation and 43 of 158 test
positives, but accepted 4 of 135 locked-test controls. Periodic magnitude,
patch consistency, and lag autocorrelation therefore expose reproducible
OpenAI renderer structure but do not meet the SynthID specificity gate.

These negative results bound the current manual feature search. Signed phase,
phase-free power, subperiods, integer and fractional scale, inverse raster
registration, spectral self-similarity, nonlinear periodic variance, spatial
consistency, and second-order lag products have all either lost sensitivity or
crossed held-out controls. Adding further hand-selected transforms to the same
exposed corpus would increase adaptive overfitting rather than confidence. A
defensible next OpenAI epoch requires provider-authorized oracle labels or
clean same-content counterfactual pairs and a fresh temporal holdout.

An untouched 2026-08-07 through 2026-08-10 temporal cohort supplied that
holdout for validation, but not the missing oracle negatives. It contained 486
explicit OpenAI-provenance positives and 504 heterogeneous controls. Only seven
additional files were pure OpenAI C2PA candidates without a SynthID assertion;
the remaining same-platform candidates contained inferred or mixed Google and
OpenAI watermark provenance and were not treated as clean negatives. The frozen
signed period-8 candidate accepted 5 of 486 positives and 1 of 504 controls.
The phase-free period-16 candidate accepted 2 of 40 supported positives and 1
of 50 supported controls. The nonlinear period-4 candidate accepted 14 of 486
positives and 8 of 504 controls. The manual carrier branches fail temporal
transfer.

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

The same untouched August cohort then challenged the frozen 512-square forensic
model and its unchanged threshold. It accepted 82 of 486 explicit OpenAI
positives, one of 504 heterogeneous controls, and one of seven pure OpenAI C2PA
candidate controls. The aggregate score separation was real, but transformation
testing resolved its interpretation: all 82 native detections disappeared after
both JPEG-95 and WebP-95 round trips. A 0.75x resize retained 46, and a 5% crop
retained 23. The model therefore generalizes as a fragile OpenAI export
noiseprint, not as the documented robust SynthID signal.

The provider-key alternative was then tested directly. OpenAI training folds
were clustered into 1, 2, 4, 8, 16, or 32 spherical period-8 cube-root-LMS
directions, and the cluster count was selected on validation only. Eight
directions raised the development-test result from 16 to 27 of 158, with one
of 135 heterogeneous controls and two of 52 action-derived same-provider
controls accepted. This did not reveal eight independent codewords: the two
dominant clusters contained 234 of 283 training rows, and their templates
correlated at 0.982 natively and 0.924 after JPEG-95.

The frozen multi-direction model accepted none of 443 Google native-geometry
files, but accepted 5 of 39 Microsoft Designer files and 123 of 674 OpenAI-
platform files. All five Microsoft hits had joint `Microsoft, OpenAI`
provenance, one explicitly asserted an OpenAI SynthID watermark, and all five
selected the same dominant direction as 111 OpenAI hits. On the
fresh August native-geometry cohort, SHA-256 grouping reduced seven OpenAI row
hits to five unique content groups; two unique Microsoft controls crossed the
same dominant direction. A sign-invariant carrier-subspace fit retained only 1
of 158 development-test positives and none of 40 fresh positives. A final
OpenAI direction orthogonal to Google, Microsoft, and other-provider train
means likewise retained 1 of 158 and none of 40. The measured period-8 family
is distinct from Google but is shared with a Microsoft/OpenAI lineage.

Regrouping by the signed watermark assertion found 115 of 589 explicit OpenAI-
SynthID files accepted, against 13 of 117 OpenAI-lineage files without an
assertion, none of 443 Google files, and one of 89 other-provider files. The
aggregate one-sided exact-test result was `p = 0.0179`; the already exposed
development-test split was not independently significant at 27 of 159 versus
2 of 25 (`p = 0.202`). Missing watermark action is not an oracle-negative
label, so this is compatible with a provider-keyed family but does not prove
that the measured component is the watermark.

The frozen score did exhibit real codec persistence. WebP-95 retained 24 of 27
native development-test detections and added nine other positives, with the
same one of 135 controls retained. JPEG-90 retained eight of 27 and added no
positive, with zero controls. A 0.75x resize and 5% crop retained none. The
result is stronger than the full-image noiseprint and supports a genuine
OpenAI/Microsoft raster-phase component, but its geometric fragility excludes
it as the documented complete robust SynthID decoder surface.

The broader SynthID architecture permits provider-specific codes without
requiring one shared pixel template. The SynthID-Image paper separates binary
detection from payload recovery, identifies payloads as a mechanism for
distinguishing customers of one service, and assigns watermark versions to the
encoder. OpenAI and Google can therefore use the same watermark family while
deploying different encoder versions or payload distributions.

The narrower same-carrier/different-phase prediction was challenged directly.
Period-8 cube-root LMS folded residuals were collected from 581 byte-unique
OpenAI-asserted files, 443 Google-asserted files, 93 OpenAI-lineage files with
no watermark assertion, and 82 other-provider controls. Both provider
contrasts were internally stable across deterministic halves. Raw phase-free
power means had cross-provider cosine 0.480, but this shared imaging background
disappeared after subtracting the respective controls: positive power support
had cosine 0.0123, bootstrap median 0.0232 with a 95% interval of 0.0009 to
0.0856, and no overlap among the 12 strongest coordinates. The three
per-channel cosines were all at most 0.0155. The signed contrasts were negative,
not phase-locked. The evidence therefore rejects a simple Google template with
an OpenAI phase or payload substitution. It remains compatible with a distinct,
content-dependent SynthID encoder version and motivates separate learned
experts rather than further rotation of the Google carrier.

A fixed three-query OpenAI Verify validation then established attribution while
also falsifying completeness. An asserted OpenAI image accepted by the frozen
eight-direction period-8 candidate was submitted both in its original form and
as a pixel-identical PNG re-encoded without metadata. Both returned `SynthID
detected` and `Content Credentials not detected`. A second asserted OpenAI
image rejected by the local candidate, with native/JPEG scores 0.709/0.657
against thresholds 0.918/0.923, was also re-encoded without metadata; it
returned the same pixel-only SynthID verdict. The period-8 family is therefore
a genuine OpenAI SynthID component with known oracle-positive false negatives,
not merely an export fingerprint and not a complete detector. No adaptive
oracle sweep followed: OpenAI's Content Provenance documentation explicitly
disallows repeated queries to reverse-engineer, remove, or evade a watermark.
The next local epoch must treat period-8 as one expert and discover complementary
content-dependent experts using frozen corpus splits, without oracle-guided
feature selection.

Relaxing the eight-direction model to a separate validation-control threshold
for every direction increased validation recall to 36 of 140 with zero of 145
controls, but it did not preserve specificity. The locked development test
accepted 46 of 158 OpenAI rows and 4 of 135 controls. A wider provider challenge
accepted 180 of 603 explicit OpenAI-SynthID rows, 15 of 80 OpenAI-lineage rows
without an assertion, 6 of 443 Google rows, and 7 of 112 other-provider rows.
The fresh temporal result was 13 of 40 OpenAI rows, 4 of 50 general controls,
and 1 of 3 same-provider controls. The oracle-positive local false negative did
cross direction 4 under this relaxed calibration, but that direction survived
only 1 of 4 leave-one-positive-out refits; the oracle-positive row itself then
failed its JPEG threshold. Direction-specific thresholds therefore expose
unstable minority clusters rather than additional validated codewords.

A train-only bilinear follow-up tested whether a content-dependent or keyed
phase varies between images while retaining native-to-JPEG covariance within
each image. It subtracted the control within-class cross-covariance from the
OpenAI cross-covariance, selected the positive-eigenvalue rank on validation,
and kept the threshold above every validation control. Rank 1 retained only 1
of 158 locked-test OpenAI rows and zero of 135 controls, then zero of 40 fresh
OpenAI rows and zero of 53 fresh controls. A single codec-stable variable-phase
subspace is therefore rejected as the missing complementary expert.

Taking local spectral magnitude before spatial averaging produced a superficially
stronger complementary signal. Eighteen period, block-normalization, and spectral
variants were screened on validation; period-8 unit-block log-magnitude retained
8 of 158 locked-test OpenAI rows and zero of 135 controls, then 3 of 40 fresh
OpenAI rows and zero of 53 fresh controls. None of the three fresh hits overlapped
the frozen global eight-direction hits, and only one overlapped the unsafe
per-direction union. Both oracle-positive images, including the known local
false negative, remained below this expert's thresholds.

The full provider challenge rejected watermark attribution despite that clean
development transfer. The local-spectrum expert accepted 17 of 603 explicit
OpenAI-SynthID rows, 5 of 80 OpenAI-lineage rows without an assertion, zero of
443 Google rows, and 2 of 112 other-provider rows; both other-provider hits were
Microsoft. Explicit watermark assertion was not enriched over same-lineage
non-assertion (`p = 0.966`, one-sided exact test in the required direction).
Recalibrating both frozen view thresholds above the 32 same-lineage validation
maxima reduced locked-test recall from 8 of 158 to zero. Local pre-aggregation
magnitude therefore reveals another OpenAI/Microsoft raster component, not a
defensible complementary SynthID expert.

The proposed directional-wavelet branch was also tested directly on OpenAI.
A three-level DTCWT over the period-8 cube-root-LMS residual screened all six
orientations, the diagonal and axis-near groups, individual levels, and complex,
magnitude, and phase statistics. Validation selected all-orientation normalized
complex correlation at 19 of 140 OpenAI rows and zero of 145 controls. It
retained 16 of 158 locked-test OpenAI rows and zero of 135 controls, followed
by 2 of 40 fresh OpenAI rows and zero of 53 fresh controls.

This is a stronger representation of the known phase carrier, not a new expert.
Both fresh hits were already accepted by the frozen eight-direction model, the
known oracle-positive local false negative remained negative, and the other
oracle-positive row missed only the DTCWT JPEG threshold at 0.894 versus 0.897.
The provider challenge accepted 77 of 603 explicit OpenAI-SynthID rows, 3 of 80
OpenAI-lineage non-assertions, zero of 443 Google rows, and 2 of 112 other rows,
both Microsoft. The explicit-assertion enrichment was real (`p = 0.00879`), but
72 of the 77 hits overlapped the signed phase expert and their union increased
its explicit count only from 115 to 120. Same-lineage calibration retained 4
of 158 locked-test and 1 of 40 fresh OpenAI rows, while one Microsoft test row
still crossed.

The transform challenge then falsified operational shift invariance. Cyclic
rolls by `(1, 1)` and `(3, 5)`, a 0.75x resize round trip, and a 5% crop round
trip each retained zero of the 16 baseline detections. JPEG-90 retained four.
WebP-95 retained 15, accepted 25 OpenAI rows in total, and introduced one of
135 controls. DTCWT therefore improves codec tolerance for the already measured
raster phase but does not solve registration, scale, arbitrary resolution, or
the missing OpenAI payload variants.

Selecting the best DTCWT magnitude and phase candidates within their own
families did not change that conclusion. The off-diagonal magnitude candidate
retained 10 of 158 locked-test OpenAI rows and zero of 135 controls, then 3 of
40 fresh OpenAI rows and zero of 53 controls. All three fresh hits were already
signed-phase hits. The near-vertical phase candidate retained 9 of 158 and zero
of 135, but failed temporally at 1 of 40 OpenAI rows versus 3 of 50 general
controls. Magnitude also retained zero of its ten baseline detections after a
one-pixel roll, `(3, 5)` roll, resize, or crop; JPEG-90 retained one and WebP-95
retained two. Taking magnitude only after periodic complex folding preserves
the phase-origin dependency and does not realize DTCWT's intended shift
invariance.

A final DTCWT screen removed periodic folding entirely and summarized global
energy over six orientations and three levels. Nine validation-screened
translation-insensitive magnitude, power, orientation, and robust-quantile
statistics selected median magnitude proportions within each level. The locked
test accepted only 5 of 158 OpenAI rows and 1 of 135 controls; the fresh holdout
accepted zero of 40 OpenAI rows and zero of 53 controls. DTCWT therefore presents
a measured tradeoff in this corpus: preserving the periodic complex field
retains the real OpenAI carrier but its phase origin, while pooling enough to
be translation insensitive removes the transferable separation.

A metadata-stratified audit then tested whether the 77 provider-challenge hits
were confined to one encoder rollout or geometry. Within the exact `OpenAI
Media Service API` cohort, the frozen DTCWT expert accepted 75 of 581 asserted
rows and 1 of 52 same-generator rows without an assertion. Asserted-row rates
were 3/16 in May, 46/365 in June, and 26/200 in July, and 6/47, 44/320, and
25/214 across the three native geometries. The native/JPEG minimum score had
0.721 AUC against the same-generator non-assertion stratum. The component is
therefore continuous across time and geometry rather than a short-lived export
cohort, although missing assertion remains an indeterminate label rather than
a clean watermark negative.

A prespecified shift-invariant follow-up sorted all 64 cyclic period-8
template correlations within each image. This preserves the shape of the
correlation orbit while discarding its absolute phase; one train-only contrast
was fitted for native and JPEG-95 views, with both thresholds placed above all
145 validation controls. The individual views retained 5 and 7 of 140
validation positives, but their conjunction retained none of 158 locked-test
positives and none of 135 controls. JPEG, WebP, resize, and crop could not
rescue a baseline detection because there was none. Thus the transferable
OpenAI evidence is carried by signed raster phase, not merely by a
shift-invariant matched-filter peak shape.

Content-hash grouping also corrected the temporal denominators. The 486 OpenAI
rows represented 417 unique byte groups, and the 234 Google rows represented
211. The signed OpenAI period-8 result became 4 of 417 unique positives versus
1 of 454 general-control groups; the full-image noiseprint became 68 of 417;
the Google runtime result became 153 of 211. Repeated uploads did not change the
decision, but row-level counts must not be treated as independent evidence.

### 2026-08-13: OpenAI low-texture phase and masking-alignment challenge

The dominant 1086x1448 export geometry supplied 2,265 byte-unique images with
an explicit OpenAI SynthID assertion, 830 general controls at the same geometry,
and 26 OpenAI-lineage files without a watermark assertion. The exact-geometry
split contained 1,124/579/562 asserted OpenAI train/validation/test rows and
399/203/228 general controls. The lineage rows remained an indeterminate
stratum rather than being relabeled as negatives.

A train-only cross-image phase model selected 256 RGB bins from the 20
lowest-texture references in each of three luminance groups. It used
polarity-invariant axial phase and scored both native pixels and a JPEG-95 view
after canonicalizing to 512 square. Independent train halves shared only two
of 256 exact channel-frequency bins and three spatial coordinates. The full
model produced native AUC 0.526 on validation and 0.512 on test; JPEG-95 AUCs
were 0.521 and 0.512. A threshold above every validation control accepted none
of 562 test positives, while a validation 1% FPR threshold accepted four
positives and two of 228 test controls. Texture quartiles did not reproduce a
useful exception. The common absolute-phase hypothesis is rejected for this
OpenAI geometry.

The official architecture points to a different mechanism: watermark
generation is deliberately content-dependent to resist watermark exchange,
and nearly uniform content can be filtered rather than watermarked. A second
frozen probe therefore discarded absolute phase and global residual amplitude.
It measured 60 OKLab relations between blockwise high-frequency energy and
local texture, contrast, and chroma at two filter scales and two block sizes.
One train-only shrinkage-Fisher direction was scored in native and JPEG-95
views, and the joint decision used their minimum above every validation
control. Joint AUC was 0.563 on validation and 0.593 on test. The frozen test
count was 15 of 562 asserted OpenAI rows and one of 228 controls.

That weak enrichment was not a stable expert. Directions fitted on deterministic
train halves had raw-coordinate cosine 0.148. One half accepted 13 test
positives and two controls, the other accepted none; their test score
correlations were 0.335 on positives and 0.127 on controls, with no overlapping
positive decision. The branch is rejected as an unstable content or export
correlate. Together these experiments reinforce the existing boundary: a new
OpenAI epoch needs pixel-oracle labels or clean same-content counterfactuals,
not further adaptive feature selection on provenance-labeled exports.

### 2026-08-13: multi-scheme domain generalization and Gemini bicoherence

A deliberately broader experiment tested whether SynthID could inherit a
generic post-hoc watermark signature instead of a provider carrier. Ninety
source-matched COCO pairs were prepared for each of TrustMark P, Meta VideoSeal
Y-256, classical 64-bit DWT-DCT, and Meta WAM-MIT, always with random payloads.
The official VideoSeal decoder recovered a mean 99.6% of bits across identity,
JPEG-90, 0.8x resize round trip, and 5% crop round trip; its mean pair PSNR was
45.04 dB. WAM recovered 99.5-99.6% across the same views at mean PSNR 38.44 dB.
DWT-DCT supplied an architecture-diverse control, but only identity and resize
were retained as positives because its official decode collapsed to chance
after JPEG and crop.

A sign-symmetric 3,900-feature spatial rich model first learned residual
co-occurrences in luminance, opponent-color, and Lab channels. Its linear and
quadratic paired-delta variants recognized familiar schemes but did not transfer
to a held-out scheme. A stronger neural follow-up used a fixed residual bank,
worst-family training, cross-family residual transplantation, random sign,
phase, and amplitude, plus phase-scrambled equal-power residuals as hard
negatives. Each of four runs withheld one complete encoder family and all test
source images. Held-out aggregate AUCs were 0.562 for TrustMark, 0.474 for
VideoSeal, 0.497 for DWT-DCT, and 0.437 for WAM. The corresponding strict
true-positive rates were 5.0%, 3.3%, 0%, and 0%. This rejects the available
open-proxy path to a universal single-image detector: even causal paired data
from three distinct schemes did not generalize to a fourth.

A separate Gemini experiment tested a translation-invariant higher-order
signature. Block bicoherence measured normalized phase coupling at period-16
triplets satisfying `f1 + f2 = f3`; unlike ordinary phase correlation, the
global image-shift phase cancels from this product. Six Green, cube-root LMS,
and OKLab representations, two residual scales, two block sizes, and three
train-only harmonic counts produced 72 candidates. The data were separated
into harmonic-fit, candidate-selection, threshold-calibration, and final
splits: 30/20/50 Gemini positives and 100/100/100/199 Open Images controls.
The best selection candidate accepted none of 20 positives at the selection
control maximum and had AUC 0.523. After independent recalibration, the final
result was 0 of 50 Gemini positives and 0 of 199 controls, with AUC 0.374.
Period-16 bicoherence is therefore rejected as a scale or origin rescue. The
measured Gemini carrier remains a linear, registered periodic tile rather than
a transferable harmonic cascade.

### 2026-08-14: remaining Gemini resolution challenges

The 0.5x gap was tested with a local-consensus detector rather than another
global period-8 score. Each half-scaled image was divided into 64-pixel patches;
the 90th percentile of full-template patch correlations was selected without
using the locked test. It accepted 33 of 49 validation positives and zero of 166
validation controls at the frozen 0.552176 threshold, then 27 of 52 locked-test
positives and zero of 140 controls. This looked like a useful low-resolution
expert but did not survive scale-matched specificity testing.

The frozen challenge symmetrically resized every remaining Spaces control and a
separate 1,000-image Open Images reserve to 0.5x. The expert accepted 61 of
10,906 Spaces controls and 22 of 1,000 Open Images controls. All 83 errors were
rescored with the prespecified feature inventory. A negative-Green patch-spread
gate could remove them post hoc, but retained only 12 of 106 base-positive
development hits. On the later August 7-10 cohort the original patch expert
accepted 67 of 234 Google-provenance rows and 8 of 689 controls, while the new
conjunction retained only 2 Google rows and zero controls. The broad challenge
rejects the base expert and the temporal result rejects the post-hoc repair.
No 0.5x claim is added.

The large-image window family was completed separately. One centered,
phase-aligned 2,048-square registered window accepted 1 of 37 candidates above
10 megapixels and zero of 89 controls. Scoring every phase-aligned 2,048-square
window and accepting the maximum raised recall to only 2 of 37, still with zero
controls; the maximum control decision score was already 0.9677 against the 1.0
runtime boundary. Together with the previously rejected fixed-window consensus
and full-frame resize, these results leave the 10-megapixel ceiling intact.

Near-ceiling windows, color spaces, and JPEG-paired phase directions did not
provide a missing large-image expert. Three aligned windows of approximately
10 megapixels retained 1 of 37 candidates and zero of 89 controls. A native
fixed-score plus Green mid-band rule retained 15 of 19 candidates in four exact
recurring geometries and accepted one of 11,417 resized Spaces controls, but
collapsed to 0 of 19 after JPEG 90. A codebook fitted to the minimum native/JPEG
period-16 correlation selected RGB Green mid-band on the pre-July split. It
retained 23 of 26 candidates and zero of 40 controls there, then 10 of 11 and 7
of 49 on July. Lab and OKLab candidates failed on the same hard control. The
apparent native signal is a codec or upscaler lattice rather than a robust
watermark invariant.

Those 37 candidate labels came from Google C2PA and an inference that Google
media is likely watermarked, not an individual Google pixel-decoder result.
They cannot support a production recall claim. The next large-image step is an
immutable SHA-to-verdict Gemini batch, followed by fitting only on
oracle-detected files. The first live attempt on 2026-08-14 was stopped by
Google reCAPTCHA before the first new file submission; no CAPTCHA bypass was
attempted.

### 2026-08-14: official large oracle and opponent-color runtime branch

The frozen Gemini batch was subsequently submitted without bypassing CAPTCHA.
Every submitted file had AI provenance removed while preserving the decoded
RGBA fingerprint. Google returned a pixel-positive verdict for seven of seven
usable submissions across 3072x5504, 5504x3072, 5632x3072, 6336x2688,
3584x4800, 5016x3328, and 4096x4096. An eighth case was indeterminate after the
verifier quota ended. This is direct evidence for seven positives, not a label
upgrade for the remaining 30 C2PA-inferred candidates.

Revisiting the native period-16 fold by opponent color exposed the missing
separation. Google candidates preserve strong Red-minus-Green and
Blue-minus-Yellow phase agreement across every phase-aligned 2048-square
window, while natural resize aliases do not preserve the complete conjunction.
The frozen large-v1 rule requires minimum fixed score `0.14`, minimum
Red-minus-Green spatial correlation `0.90`, minimum Blue-minus-Yellow spatial
correlation `0.70`, and a minimum signed Blue-minus-Yellow mid-band correlation
at or below `-0.15`. The 3072x5504 portrait geometry additionally requires the
maximum Green mid-band correlation to stay at or below `0.06`. Its public score
is the minimum normalized gate margin and crosses at `1.0`.

The rule retained all 37 inferred candidates, including all seven official
pixel positives. It accepted none of 17,417 exposed COCO, Open Images, and
Spaces controls after the portrait alias gate. Because those controls informed
the final gate, they do not certify the operating point. The constants were
then challenged through the actual runtime on a frozen, decoded-pixel-deduped
local holdout: 2,000 COCO val2017 images excluded from the earlier 3,000-image
large color-phase challenge plus 637 unique Picsum controls deduplicated from
1,000 files. Four large geometries and four resampling kernels were balanced.
The result was 0 of 2,637 detections, with maximum score `0.0592777965`; the 95%
zero-error upper bound is about 0.114%. These source collections existed before
the freeze and supported other experiments, so the result is feature-unseen
rather than a fresh-acquisition holdout.

The post-freeze Open Images acquisition was too slow to complete the planned
3,000-image challenge, but its completed subset provides an independent source
audit. Incomplete `.aria2` files, all prior Open Images decoded-pixel hashes,
and duplicates were excluded before scoring, leaving 41 controls whose IDs and
URLs had been frozen after the constants. The unchanged runtime accepted 0/41;
the maximum score was `0.4083013324`. This small audit supports the source
boundary but does not replace the 2,637-control feature-unseen interval.

A prespecified post-freeze codec stress test re-encoded the seven official
positives at unchanged dimensions. Native detection was 7/7, while JPEG-95 and
JPEG-90 were each 0/7. Thresholds were not refitted. Large-v1 is therefore a
native-pixel and lossless-copy detector, not a lossy-transcode detector.

The old fixed-only rule still crosses on four locally saved rows representing
three unique pixel groups. One group is an Adobe file whose C2PA explicitly
reports Google SynthID present. The other two remain queued for an official
Gemini verdict and are not counted as clean negatives. The runtime branch is
therefore positive-only and does not turn a miss into an absence claim.

Production routing now selects the fixed expert from 1 through 10 megapixels
and the large expert above 10 through 18 megapixels when both sides are at least
2048 pixels. The score exporter emits fixed, registered, and large observations
separately, preventing the large result from being mislabeled as a fixed score.
The router accepts a registered or large threshold crossing only within that
expert's measured scope and otherwise abstains.

### 2026-08-14: final OpenAI local rescue checks

An assertion-contrast probe at the dominant exact 1254-square geometry tested
RGB, OKLab, and cube-root-LMS period-8 channel directions without treating
missing assertion as a clean label. Validation selected `srgb:p8:c2`, accepting
45 of 259 asserted rows and zero of 13 same-provider plus three other-provider
rows. The locked test accepted 39 of 233 asserted rows, zero of 15 same-provider
rows, and one of three other-provider rows. The all-row audit accepted 185 of
992 asserted rows, one of 55 same-provider rows without an assertion, and one
of 13 other-provider rows. A safe boundary above either wider control maximum
retained only a small minority of the asserted cohort. Exact geometry therefore
does not turn the weak OpenAI component into a production detector.

An independent published-decoder veto was then tested with the official
InvisMark checkpoint. The downloaded checkpoint hash was fixed before use, and
its bundled self-test reached 0.997 mean confidence with 0.97 recovered-bit
accuracy. In contrast, OpenAI DTCWT hits, OpenAI misses, exact-1254 hits and
misses, same-provider controls, Google, Microsoft, Canva, and unrelated controls
all had median confidence near 0.18. The decoder is working, but its watermark
family is absent from these cohorts; it cannot distinguish SynthID-bearing
OpenAI pixels from renderer confounds.

Two representation-level missing-codeword hypotheses were also rejected.
DTCWT modulus computed before spatial period folding selected off-diagonal
phase coherence and retained 5 of 158 locked-test OpenAI rows versus zero of 135
controls, but zero of 40 fresh OpenAI rows. Whitening the period-8 feature space
and clustering up to 16 codewords retained 5 of 158 and zero controls, then one
of 40 fresh OpenAI rows and one of 50 fresh controls. Neither captured the known
oracle-positive false negative. These were the remaining prespecified phase,
wavelet, codeword, and external-decoder variants; none earns a local runtime
route.

### 2026-08-14: production OpenAI verifier boundary

OpenAI's official Content Provenance API now supplies the production-grade
OpenAI pixel verdict that the local experiments could not justify. The runtime
integration is deliberately a separate `verify-openai-synthid` command, never
an implicit `identify` call. It requires the independent `verify` extra,
`OPENAI_API_KEY`, endpoint access, and `--acknowledge-upload`.

The implementation establishes metadata independence before the request. It
computes a decoded RGBA fingerprint, strips AI provenance metadata to a
temporary copy, verifies that no AI markers survived and that the format and
pixel fingerprint stayed identical, enforces the documented 50 MiB limit, and
uploads only the temporary PNG, JPEG, or WebP. It parses exactly one `synthid`
entry and deliberately ignores the independent C2PA outcome. C2PA-only
positives, missing or duplicate SynthID fields, altered pixels, surviving
metadata, unsupported formats, and 400/404/429 failures are covered by mocked
tests. No credentialed API request was made during implementation because no
API key was available.

A separate live smoke used OpenAI's public web verifier after running the exact
production metadata-stripping and decoded-RGBA equality checks. Two OpenAI
images at opposite 3:2 orientations returned `SynthID detected` and `Content
Credentials not detected`. A Google SynthID oracle-positive control and a COCO
natural control returned OpenAI `SynthID not detected`, again with Content
Credentials absent. This confirms pixel-only, provider-specific semantics for
the integration, but four fixed cases do not estimate statistical error rates
and do not constitute a live SDK/API transport test.

This closes the production OpenAI detection surface through an official remote
backend, not by relabeling the incomplete local period-8 expert. It does not
expand the research oracle authority. The endpoint is not eligible for Zero
Data Retention, and its documentation prohibits repeated reverse-engineering or
evasion queries, so it cannot supply adaptive labels for detector or remover
optimization without separate authorization.

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

## Historical first milestone

The first local-research milestone was defined to produce evidence rather than
shipping code. Its scope was:

1. the private-corpus schema and auditor;
2. an OpenAI authorization decision for use of the remote provenance verifier;
3. an independently verified status for candidate causal pairs;
4. a canonicalized OpenAI pilot set with hard negatives;
5. the D1 confound report;
6. the D2 low-texture carrier report with leave-one-group-out results;
7. a go or no-go decision for real-image detector training.

The completed experiments produced a no-go decision for a local universal
OpenAI detector. The later official remote backend is a separate production
route and does not retroactively turn provenance-labeled exports into pixel
oracle training data.

## Primary sources

- OpenAI, [Content provenance](https://developers.openai.com/api/docs/guides/content-provenance).
- OpenAI, [ChatGPT Images 2.0 system card](https://deploymentsafety.openai.com/chatgpt-images-2-0/automated-evaluations-and-adversarial-testing).
- Google, [Verify AI-generated images, videos, and audio](https://support.google.com/gemini/answer/16722517?hl=en).
- Gowal et al., [SynthID-Image: Image watermarking at internet scale](https://arxiv.org/abs/2510.09263).
- Meta, [VideoSeal](https://github.com/facebookresearch/videoseal).
- Meta, [Watermark Anything](https://github.com/facebookresearch/watermark-anything).

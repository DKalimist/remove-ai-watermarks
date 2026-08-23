# SynthID: technical reference

> Technical research reference for the mark itself and for what this package
> ships. Current package behavior is defined by the
> [supported signals](supported-signals.md), [known limitations](known-limitations.md),
> and [module internals](module-internals.md). Campaign results are split:
> [local detector](synthid-detector-research.md),
> [classifier models](synthid-classifiers.md),
> [mark removal](synthid-removal-research.md). Dated measurements below are
> historical evidence and should not be read as current CLI defaults.

This document covers how Google SynthID for images works mechanically, what it
survives, what removes it, the external video-verification workflow, and the
current deployment landscape. It is written for engineers working on watermark
detection and removal -- specifically to inform decisions about strength
settings, test methodology, and what oracle results mean.

Primary sources are cited inline. Marketing-only claims are flagged separately
from independently-verified results.

---

## 1. Mechanism

### 1.1 Post-hoc, model-independent design

SynthID-Image is **not** baked into a diffusion model's weights. It is a
post-hoc, model-independent system: a separate encoder `f` is applied to an
already-generated image, and a separate decoder `g` reads it back.

> "We deliberately designed SynthID-Image as a post-hoc, model-independent
> approach, a choice largely based on deployment considerations."
> -- Gowal et al., arXiv:2510.09263

The formal definition from the paper:

> "A post-hoc watermarking scheme is a pair f, g consisting of an encoder
> function f: X -> X, which adds an identification mark, and a decoder
> function g: X -> {+-1}, which tries to detect if the mark is present."

This is the key architectural fact: **the generative model (Imagen, Gemini's
image model) is not modified**. The watermark is stamped onto the pixel output
after generation, by a separate neural network. This means:

- The watermark is in **pixel space**, not in the model's latent activations.
- Replacing the generative model does not remove the watermarking capability.
- The encoder/decoder pair can be updated independently of the generative model.

The detector's training target is narrower than provider or AI-image
classification. Equation 1 trains on watermarked `f(x)` as positive and the
corresponding unwatermarked distribution `x` as negative, with both drawn from
the same target image distribution. Equation 2 applies the same sampled
semantics-preserving transformation to both sides. Unrelated generators and
camera images are useful later for false-positive evaluation, but they do not
replace source-matched clean examples during signal-identifiability training.

The decoder produces a dedicated detection logit whose threshold is calibrated
after training for a target false-positive rate. Payload recovery is a separate
problem, not the definition of the presence score. The paper additionally
describes two-sided conformal calibration for the `not watermarked` and
`watermarked` hypotheses, which permits a detector to abstain instead of forcing
an unsupported binary verdict.

The paper does not disclose the internal architecture of the encoder/decoder
networks (layer types, capacity). The external variant SynthID-O is available
to partners; the production internal variant is not published.

### 1.2 Patent-backed architecture clues

A related [DeepMind patent family](https://patents.google.com/patent/US12094474B1/en),
filed in 2023 and naming several authors of the SynthID-Image paper, describes
the likely architectural design space in more detail. Patent alternatives are
not proof that every option is deployed in production SynthID, so the following
items are constraints and research clues rather than implementation claims.

The patent's image example forms a content-dependent residual, `x' = x + g(x)`.
It describes a U-Net-like watermark generator with convolution, attention, and
skip connections; a separately trained convolutional decoder; optional message
or secret-key injection into intermediate layers; and paired training on clean
and watermarked images under sampled differentiable transformations. It also
allows an image to be resized to a trained target size for watermarking and then
resized back to its original dimensions.

Most importantly for blind detection, a
[continuation patent](https://patents.google.com/patent/US20250149048A1/en)
describes groups or ensembles of paired encoder/decoder networks. A decoder can
be trained not to recognize marks from another pair, while deployment can
select one pair or combine several outputs. This supplies a concrete mechanism
for coexisting watermark versions, provider-specific states, or distinct
codewords without requiring one universal pixel template.

The fixed periodic carriers measured in this project should therefore be
treated as linear experts for particular observable states, not as the
definition of SynthID. A broader detector needs independently validated experts
for additional encoder states and transformations, followed by joint
false-positive calibration. The paper's separate detection logit and two-sided
conformal decision provide the correct target behavior: present, absent, or
abstain when neither hypothesis is supported.

### 1.3 How it differs from classical DWT-DCT watermarks

The open watermarks used by Stable Diffusion / SDXL / FLUX (via the
`imwatermark` library) use classical **DWT-DCT** frequency-domain embedding: a
fixed bit pattern is added to specific frequency coefficients of the image's
wavelet transform. This is fast, key-free, and locally detectable with a public
decoder.

SynthID-Image uses **jointly-trained deep learning models**:

> "SynthID uses two deep learning models -- for watermarking and identifying --
> that have been trained together on a diverse set of images. The combined model
> is optimised on a range of objectives, including correctly identifying
> watermarked content and improving imperceptibility by visually aligning the
> watermark to the original content."
> -- Google DeepMind blog, 2023

The practical difference for robustness: the deep learning encoder learns to
spread the signal across the image in a way that is optimized to survive a
specific perturbation distribution seen during training. Classical DWT-DCT
embeds in fixed, predictable frequency bins, making it brittle to any
operation that hits those bins (e.g., JPEG re-quantization wipes it cleanly at
quality <= 90).

### 1.4 Payload capacity

SynthID-O (the external/partnership variant) encodes:

- **136 bits** within a **512x512 pixel image**

For comparison (from the same paper):

| Method      | Bits | Resolution |
|-------------|------|------------|
| SynthID-O   | 136  | 512x512    |
| StegaStamp  | 100  | 400x400    |
| TrustMark   | 100  | 256x256    |
| WAM         | 32   | 256x256    |

The payload carries an identification mark (not a user-readable secret). The
paper separates watermark **detection** (is this watermarked?) from payload
**recovery** (what does the payload say?): the detection path is what oracles
like the Gemini app's "Verify with SynthID" exercise.

### 1.5 Where in the pipeline it lives

```
[Diffusion model]
       |
  raw pixel output
       |
  [SynthID encoder f]   <-- separate neural net, stamps the watermark
       |
  watermarked image
       |
  [served / downloaded]
       |
  [SynthID decoder g]   <-- separate neural net, run by Google's verifier only
       |
  present / not present
```

The VAE decoder of the diffusion model is **not** involved in watermarking.
Some in-generation watermark approaches (like the research method "Tree Ring")
inject the signal into the initial noise latent so it propagates through the
diffusion process and appears in the final image; SynthID-Image does not do
this -- it is applied after the VAE has already decoded latents to pixels.

---

## 2. Robustness

### 2.1 What the paper claims it survives (primary-source verified)

The SynthID-Image paper (arXiv:2510.09263) evaluates SynthID-O against **30
image transformations** grouped into 6 categories:

| Category    | Examples                                      |
|-------------|-----------------------------------------------|
| Color       | brightness, contrast, saturation, hue shifts  |
| Combination | combinations of multiple transforms           |
| Noise       | Gaussian noise, impulse noise, median filter  |
| Overlay     | text overlays, logos, stickers                |
| Quality     | JPEG compression, WebP, format conversion     |
| Spatial     | crop, resize, rotate, flip, padding           |

**TPR at 0.1% FPR -- SynthID-O vs. baselines (resized to 512x512):**

| Category         | SynthID-O | Best baseline (WAM) | Worst baseline (StegaStamp spatial) |
|------------------|-----------|---------------------|--------------------------------------|
| Identity (none)  | 100.00%   | 100.00%             | 100.00%                              |
| Aggregated       | 99.98%    | 90.62%              | ~70%                                 |
| Color            | 100.00%   | 81.29%              | ~75%                                 |
| Combination      | 99.96%    | 96.08%              | ~22%                                 |
| Noise            | 99.98%    | 100.00%             | ~92%                                 |
| Overlay          | 100.00%   | 100.00%             | 100.00%                              |
| Quality          | 99.99%    | --                  | ~89%                                 |
| Spatial (worst)  | 99.97%    | 76.04%              | 15.25%                               |

The "Spatial worst" row is the hardest case (aggressive crop + resize).
SynthID-O retains 99.97% TPR; StegaStamp collapses to 15.25%. This is where
the deep-learning approach gains the most over classical methods.

Google's marketing page states the watermark is:

> "designed to stand up to modifications like cropping, adding filters, changing
> frame rates, or lossy compression."
> -- deepmind.google/models/synthid/

The marketing claim is broadly consistent with the paper's numbers for these
specific categories.

**JPEG and format conversion specifically** fall under the "Quality" category,
where SynthID-O achieves 99.99% TPR. This is the empirical basis for the fact
that **GitHub-recompressed JPEGs from issue attachments are valid SynthID test
subjects**: the re-encoding does not remove the pixel watermark.

### 2.2 Stated limits (vendor claim, not independently verified)

> "SynthID isn't foolproof against extreme image manipulations."
> -- Google DeepMind blog, 2023

This is the only public failure-mode statement Google has made. No specific
perturbation type, threshold, or quantitative boundary is named. The
Limitations section of the paper (Section 10) was not recoverable from the
public HTML version of arXiv:2510.09263v1 due to a rendering failure in the
conversion (the body text of Section 10 is absent from the HTML).

**What is known empirically from our own oracle-verified testing.**

A 2026-08-09 non-generative pilot found a promising Google phase-correlate,
but did not establish a releasable local detector or pixel-only remover.
The 2026-08-20/22 OpenAI campaign is recorded in
[synthid-detector-research.md](synthid-detector-research.md),
[synthid-classifiers.md](synthid-classifiers.md), and
[synthid-removal-research.md](synthid-removal-research.md).
JPEG q5 and 16-32 px phase structure survive as the official mark; a
quality-preserving local remover and a local SynthID detector for
photographs were not found. `gpt-image-2` source-matched flat pairs exist;
their residual does not transfer to photographs. The
best independently fitted spectral model relearned phase and magnitude from four of our
positives while using third-party candidate coordinates; its second frozen
epoch had zero false positives on 279 new exact-size external images and
detected the one new confirmed positive used for validation. An additional
3,000 upscaled photographs all fell outside the measured active-carrier support
and therefore count as abstentions, not negatives. The corpus is still far too
small and lacks same-provider hard negatives needed for a 0.1% FPR claim.
Repeating the spectral fit in six color spaces produced zero false positives
on the same 279-image comparison set for every branch. HSV had the best
observed worst-negative margin, but paired normalized negative scores did not
show a general improvement over RGB. Its apparent benefit came from saturation
and value; hue failed its channel-level separation check. Luminance-like
channels dominated YCbCr, YCoCg, opponent, and Lab. This narrows the next
hypothesis to intensity/contrast and HSV S+V projections rather than a
hue-specific carrier, but it does not add independent positives or certify an
operating point.
The resulting positive-only RGB plus S/V ensemble passed four
leave-one-positive-out checks, detected all five available positive controls,
and emitted no positive verdict on 330 newly collected exact-size images.
Almost all external images lacked sufficient measured carrier support and
therefore remained abstentions rather than proven negatives.
A later post-freeze challenge used three additional exact-size Google originals
with signed Google LLC C2PA and explicit SynthID-present assertions. The
ensemble abstained on all three. They do not replace matching-oracle pixel
labels, but this zero-of-three source-provenance result rejects the frozen
ensemble as a general Google detector and narrows it to an epoch- or
surface-specific correlate.

A multi-epoch leave-one-positive-out refit recovered six of the eight total
Google positives under a strict RGB-plus-HSV decision; RGB alone ranked every
excluded positive above the 50-image calibration maximum but produced up to
eight false positives on 279 held-out external negatives. The signal therefore
transfers across the two source groups, but remains content-sensitive and
cannot be separated from provider or generation-pipeline attribution without
same-provider oracle-negative controls.

Directly projecting out the ensemble phases cleared the local detector above
51 dB PSNR, but three frozen candidates remained detected by Gemini in a
healthy control session. A subsequent spatial analysis found that 81.25% of
the top 256 carrier bins lie on a lattice corresponding to a repeating 16x32
pixel cell. Modulo-folding and subtracting the complete high-pass tile gave
phase-specific matched-control separation across all five Google positives at
at least 55.67 dB PSNR: aligned outputs cleared the local ensemble, while
one-pixel-shifted controls remained positive. The mild locally clearing tile
candidate nevertheless remained detected in a healthy Google Verify AI
session, so the tile correlate is not a sufficient removal loss.
Sparse subtraction reduced the local score sharply at more than 50 dB PSNR,
yet healthy Gemini sessions still detected SynthID. A one-off negative was
discarded because the same session also missed the source-positive control.
An OpenAI-specific 8-pixel phase candidate likewise changed its local score at
46.70 dB PSNR but remained `SynthID detected` in one frozen OpenAI Verify
check. No Google threshold or carrier was used in that experiment, and no
further public OpenAI checks were made because the documented verifier guidance
rules out repeated watermark-removal queries.

A later local EOT pilot combined periodic full-frame residuals with JPEG-aware
optimization against provider-specific CNN surrogates. It produced candidates
that stayed below three local models after actual JPEG round trips, but the
models remain provider classifiers without same-provider oracle-negative
controls. The selected Google candidate retained 36.80 dB PSNR and 0.9241
SSIM; the selected OpenAI candidate retained 34.97 dB and 0.9356. Both miss the
research fidelity gate. The OpenAI periodic residual also reduced all three
local model scores on 11 of 11 additional images before and after JPEG-90, but
neither provider candidate has a negative matching-provider oracle verdict, so
neither is an established remover.

A later paired open-method control tested stationary wavelet and complex
spectral representations without treating another watermark as SynthID. On a
source-disjoint TrustMark P proxy, the SWT branch moved 59 of 60 transformed
clean/watermarked pairs in the correct direction but did not improve the
spatial model's aggregate AUC. Complex FFT maps were indistinguishable from
chance, and fixed phase scoring collapsed under crop. Wavelets therefore remain
a gated late-fusion ablation, while complex spectral analysis remains a
residual-discovery tool rather than a presence score.

Expanding that proxy to four causally paired watermark families did not produce
a universal residual detector. TrustMark P, VideoSeal Y-256, DWT-DCT, and WAM
each used 90 source-matched images and random payloads; official decoders
validated which transformed positives still carried readable marks. A fixed
steganalysis residual bank and a neural model trained with cross-family
residual mixing, sign and phase augmentation, and equal-power phase-scrambled
hard negatives were evaluated leave-one-family-out. The four unseen-family
AUCs were 0.562, 0.474, 0.497, and 0.437. A network can therefore learn each
available encoder without learning a transferable class called "neural
watermark." This open-proxy route is not evidence for Google or OpenAI SynthID.

The same conclusion held on a larger temporally split closed corpus. A
three-seed normalized-patch ensemble reached 0.884 AUC, but its threshold above
all validation negatives produced a test false positive and detected only
2.45% and 8.97% of the two positive-source classes. Naive full-field pooling,
late-fused SWT, robust patch aggregation, and a separate binary detection head
did not improve that low-FPR operating point. Vendor classification was highly
accurate among accepted positives, but it cannot rescue an unreliable presence
decision. Source labels therefore remain suitable for vendor triage and hard
negative evaluation, not for establishing a SynthID detector without
counterfactual or oracle watermark labels.

A later low-content matrix also rejected wavelet energy and normalized
wavelet-shape classifiers: they separated real target outputs from artificial
flat, Gaussian, and phase-random controls, then accepted 61.6-100% of real
external negatives. The surviving branch is narrower. A provider-specific
1536x2816 phase carrier detected all four temporal-test positives, bounded
translation registration recovered all four one-pixel shifts, and the joint
phase/support rule produced zero positives on 194 frozen negatives. A
scale-and-translation discovery rule also produced zero positives on a
preregistered 3,000-image COCO challenge, but every COCO image was outside
carrier support and the scale threshold was selected post hoc. The result is
therefore a positive-only, geometry- and epoch-specific expert with abstention,
not a universal SynthID detector. Exact measurements and remaining calibration
gates are in the
[`detector and removal research plan`](synthid-detector-removal-plan.md#2026-08-10-low-content-controls-and-registered-phase-carrier).

The next native-geometry experiment isolated a stronger mechanism. At
2048x2048, 108 selected spatial frequencies formed a 128-bin lattice, implying
a 16x16 periodic residual tile. Folding and averaging 16,384 tile repetitions
produced a spatial detector that accepted 29 of 30 test positives, none of 49
calibration negatives, and none of 38 held-out test negatives. It also accepted
the same two of 182 earlier external-source images as the independent RGB and
HSV phase branches. Those cases count against operational source-label FPR,
but may contain the same carrier through an upstream encoder; only an oracle
can distinguish the two explanations. A normalized tile challenge accepted
none of 3,000 general images, while symmetric attacks showed strong resize but
limited JPEG and crop robustness. The pickle-free research implementation is
`scripts/synthid_periodic_tile_probe.py`; exact evidence and caveats are in the
[`2048 periodic-tile experiment`](synthid-detector-removal-plan.md#2026-08-10-2048-periodic-tile-detector).

The historical 2048 reports retain aggregate counts and model hashes, but not
the 111 fitting paths. A later exact-1024 audit demonstrated that perceptual
siblings can cross an image-level split despite different file and decoded-pixel
hashes, so the old 2048 train/validation/test split cannot be retrospectively
cleared of that leakage mode. Its external control challenges remain valid;
its positive rates are conditional on the historical split. The next model
calibration must preserve content-group membership across every partition.

An aligned-subtraction ablation strengthened the mechanism finding without
clearing the oracle gate. At a discovery-selected amplitude, it reversed both
the fixed-tile and independently fitted phase decisions on all 30 test images
at a median 53.74 dB PSNR and 0.99681 SSIM. The aligned edit reduced both scores
more than cyclic-shifted and orthogonal random tile controls on every paired
image. A shifted tile nevertheless suppressed the phase score enough to leave
only one accepted image, so these local reversals remain surrogate evidence,
not verified SynthID removal. The exact controls and caveats are recorded in
the linked experiment section.

A later adaptive projection reduced that local cost substantially. It repeats
the frozen unit-norm 16x16 carrier over the decoded image and uses a bounded
scalar search for the smallest subtraction amplitude that reaches a requested
fixed-tile score. There is no generative model, spatial optimizer, or change of
image dimensions. Among the 30 historical 2048x2048 ablation sources, 27 were
positive under both the fixed-tile and independent phase rules before editing.
Searching only the scalar amplitude cleared both rules on all 27 at a median
59.83 dB PSNR and 0.99890 SSIM; the minima were 55.19 dB and 0.99705. Applying
the same selected amplitudes to a one-pixel cyclic shift of the carrier cleared
none of the 27. Of the 16 sources whose carrier survived an otherwise identical
JPEG-95 round trip, aligned projection cleared all 16 after JPEG-95 while the
shifted control cleared one.

The same native-period edit works without resizing when dimensions are not
multiples of 16: repeat the carrier past both image boundaries and crop it to
the decoded geometry. A deterministic development challenge selected three
first-carrier-positive Spaces images from each of the 20 most frequent native
geometries, for 60 images total. Searching to a zero fixed-tile target cleared
60 of 60, compared with 5 of 60 norm-matched one-pixel-shifted controls. Median
fidelity was 60.37 dB PSNR and 0.99919 SSIM; the minima were 53.56 dB and
0.99581. A more conservative target score of -0.25 retained 60 of 60 native
local clearances at median 57.70 dB PSNR and 0.99863 SSIM, with minima of
52.38 dB and 0.99443.

The frozen -0.25 rule was then evaluated once on one deterministic first-carrier
positive from every native geometry represented by that Spaces subset: 647
images at 647 distinct decoded sizes. It reached the local target on all 647,
with no maximum-amplitude failure. Median fidelity was 57.67 dB PSNR and
0.99867 SSIM; the worst case was 51.78 dB and 0.99400. Among the 323 images
whose source carrier survived JPEG-95, the aligned candidate cleared 323 of
323 after the same codec round trip, compared with 58 of 323 one-pixel-shifted
controls. At the deeper transform margin, shifted controls also clear more
often natively, 153 of 647, so exact carrier phase remains causal but the edit
is no longer phase-exclusive on every content. The all-geometry corpus was
already inspected during detector development and contributes mechanism
coverage, not an independent generalization split.

The conservative target also survived every tested transform for which the
same transformed source remained locally positive: 32 of 32 JPEG-95, 13 of 13
JPEG-90, 8 of 8 JPEG-85, 15 of 15 WebP-95, and 54 of 54 0.75x resize round
trips. The shifted controls cleared 7, 1, 1, 5, and 17 of those respective
source-positive subsets. These results establish fast, geometry-independent
control over the recovered carrier and quantify the quality-versus-transport
margin. They do not establish SynthID removal. The previous provider check
showed that Google can remain positive after a locally favorable analytical
edit, and this adaptive recipe has not received a matching-provider negative
oracle verdict. It therefore remains a research candidate rather than a public
removal path.

The reproducible local tool is
`scripts/synthid_adaptive_carrier_suppress.py`. It accepts one locally positive
image, writes a lossless PNG without overwriting existing files, and records
the input/output hashes, target, selected amplitude, scores, fidelity, and
runtime in JSON. Its default -0.25 target is the transform-margin setting above.
The tool intentionally remains outside the public package CLI and refuses
locally negative inputs; its output status names carrier suppression rather
than provider-verified removal.

The immutable oracle-batch and result evaluator are implemented. On 2026-08-10,
four new 2048x2048 Gemini images were generated after the rule was frozen and
registered as a 20-request confirmatory batch. The first source group exhausted
the account's verification quota after five requests. The untouched source
returned Google C2PA Content Credentials without a separate SynthID verdict;
the lossless re-encode, aligned subtraction, and cyclic-shifted control all
still returned a Google AI signal. The orthogonal control was refused because
the quota had been exceeded, and the remaining 15 requests were not submitted.
This incomplete run is already negative evidence for the frozen pixel-only
recipe: the aligned candidate cleared the phase detector but remained positive
under the tile detector and the provider oracle. The local carrier expert
therefore ships only as a positive-only, exact-geometry detector; it is not a
universal SynthID detector or a remover.

A controlled study (June 2026, clean v0.8.6 with text/face protection OFF,
native resolution on this repo's default SDXL pipeline) measured the minimum
img2img strength that removes the SynthID pixel watermark, verified per image on
the vendor's own oracle (openai.com/verify for OpenAI, the Gemini app "Verify
with SynthID" for Google). The reusable originals are stored once in
`data/synthid/originals/`, with their input verification in `manifest.csv`.
Generated cleaned outputs are not committed; the table below is the durable
record of the historical oracle verdicts. One third-party image from issue #14
was oracle-verified but is not committed.

**Historical oracle validation order: start with OpenAI.** The June study used
the OpenAI web verifier first because it was more accessible than the Gemini app.
OpenAI now documents a Content Provenance API, but its usage guidance explicitly
rules out repeated queries for reverse engineering or watermark removal. New
adaptive experiments require separate authorization and must follow the oracle
boundary in the
[`detector and removal research plan`](synthid-detector-removal-plan.md). This is
not a cross-provider substitution: each oracle reads only its own vendor's
SynthID, so Google content still needs the Gemini flow.

| Vendor | Images | Resolution(s) | Pipeline | Removed at |
|--------|--------|---------------|----------|------------|
| OpenAI (gpt-image) | n=4 (3 archived + 1 external-only) | 1024x1536 .. 1600x1600 | native | **0.05** |
| Google (Gemini)    | n=4 | 2816x1536 -> capped 1536 | `--max-resolution 1536` | **0.15** (0.05 and 0.10 do NOT clear) |

**Two findings, both oracle-verified:**

1. **Vendor is the dominant factor, not resolution.** Google's SynthID is
   roughly 3x more robust than OpenAI's: at a comparable (small) working
   resolution, OpenAI clears at 0.05 while Google needs 0.15. This matches
   Google having hardened SynthID more aggressively over time.

2. **OpenAI SynthID removal is resolution-independent in the tested range.**
   All four OpenAI images (including a 1600x1600) cleared at 0.05.

**CORRECTION (supersedes the earlier "resolution dependence" claim).** A prior
version of this doc and CLAUDE.md stated that strength 0.30 failed to remove
SynthID on 1600x1600 gpt-image and that removal was resolution-dependent. That
was a **measurement artifact of a since-removed per-region re-scrub step** (issue
#14): on the dense-text infographics tested, that step could reconstitute SynthID
in text regions. Re-running the *same* 1600x1600 image on the clean current
pipeline removes SynthID at **0.05**. The "large images resist removal" conclusion
was false; the resistance was that region-rescrub shielding, since removed.

**Open / not locally testable:**

- **Native large Gemini (2816x1536, ~4.3 MP).** The Gemini floor of 0.15 was
  measured on the *capped* (`--max-resolution 1536`) path, which is the
  practical local route on Apple-Silicon (native 2816 OOMs / falls back to slow
  CPU on a 32 GB M-series). Native large Gemini was not measured here; the
  vendor and resolution effects would stack, so it plausibly needs >= 0.30 or a
  discrete GPU. Confirm on a CUDA box if needed.
- **Heavy JPEG compression** (quality < ~50-60): not oracle-tested; the DL
  approach is more robust than DWT-DCT but Google acknowledges limits at
  "extreme" manipulation.

### 2.3 Removal attacks and forensic detectability

The paper arXiv:2605.09203 ("Removing the Watermark Is Not Enough",
Goonatilake & Ateniese, 2026) evaluates 6 removal attacks against a ResNet-50
forensic detector. All attacks defeat the watermark verifier but are detected
by the forensic classifier:

| Attack          | Family           | AUROC  | TPR @ 1% FPR | TPR @ 0.1% FPR |
|-----------------|------------------|--------|--------------|----------------|
| UnMarker        | Distortion       | 0.9994 | 99.81%       | 98.28%         |
| WatermarkAttacker| Regeneration    | 0.9997 | 99.95%       | 99.38%         |
| CtrlRegen+      | Regeneration     | 0.9999 | 99.97%       | 99.64%         |
| NFPA            | Inversion/Pert.  | 0.9984 | 99.24%       | 62.10%         |
| Boundary Leak.  | Inversion/Pert.  | 0.9991 | 99.24%       | 88.34%         |
| WiTS            | Erosion          | 0.9999 | 99.80%       | 99.55%         |

The forensic detector is a standard ResNet-50 fine-tuned end-to-end; no exotic
architecture needed. The key finding:

> "These removers do not return images to a clean forensic state. They often
> trade an explicit watermark for an implicit watermark: a detectable artifact
> introduced by the removal process itself."

This means: even when our SDXL img2img pass defeats the SynthID pixel
watermark (oracle reads negative), the output may still be classifiable as
"an image that went through a removal pipeline" by an independent detector --
even if that detector is not trained on SynthID specifically. **Defeating the
verifier does not restore forensic deniability.**

CtrlRegen+ is the most detectable removal method (AUROC 0.9999), which is
notable because it is also the most powerful removal attack. The paper notes
that diffusion regeneration "leaves a strong reconstruction signature from the
diffusion prior."

A newer [MarkNull study](https://arxiv.org/abs/2608.10166), accepted at USENIX
Security 2026, evaluates a no-box latent-space attack on 20 Imagen-3 images and
checks the outputs with Gemini's SynthID verification flow. MarkNull, its
amortized variant, and most advanced regeneration or adversarial baselines
reached 100% attack success in that small evaluation; a simple VAE round trip
reached 0%. The per-image method inverts the input with a clean public diffusion
proxy, optimizes its latent to decorrelate the reconstructed initial noise, and
constrains LPIPS, MSE, and SSIM before decoding it again.

This is important independent evidence that removal need not know SynthID's
carrier or decoder, but it is still a generative latent reconstruction, not the
pixel-only analytical path pursued here. The paper's milder SynthID setting
reports PSNR 25.36 dB and SSIM 0.80 at 100% attack success. Those values do not
meet this project's 40 dB median PSNR and 0.99 median SSIM release gate, despite
the paper's favorable composite quality score. MarkNull-A's reported 0.50-second
runtime and 6.3 GB VRAM are attractive as a future optional fallback, but they
do not establish a fast, visually lossless pixel-only remover.

---

## 3. Detectability and verifier access

### 3.1 No public payload decoder

The SynthID decoder is proprietary and not released:

> "SynthID-Image has been used to watermark over ten billion images and video
> frames across Google's services and its corresponding verification service is
> available to trusted testers."
> -- Gowal et al., arXiv:2510.09263

There are no released payload-decoder weights or public algorithm. Google
provides verification in Gemini and a limited SynthID Detector
portal. OpenAI now documents a synchronous Content Provenance API whose image
response contains separate C2PA and SynthID outcomes. That API is a remote,
OpenAI-scoped verifier, not a local decoder. Its documentation also says not to
use repeated queries to reverse-engineer, remove, or evade a watermark, so an
adaptive research loop requires separate authorization.

Google's SynthID Detector service is:

> "a verification portal" in early testing with "journalists and media
> professionals" on a waitlist
> -- deepmind.google/models/synthid/

The external variant SynthID-O is available "through partnerships" only. This
project instead detects one empirically recovered periodic carrier family in a
calibrated image-size range. It does not decode the proprietary payload or
generalize that local signal to unsupported sizes,
codecs, video, or future epochs. The evidence and gates are documented in
[`synthid-detector-removal-plan.md`](synthid-detector-removal-plan.md).

### 3.2 How our tool detects the supported carrier

The heading is kept because README, `cli.md` and `python-api.md` link to this
anchor, but the name is inherited and inaccurate. What the local experts read
is a periodic lattice anchored at the image origin, measured on 2026-08-16 to
vanish under a seven-pixel crop that the published SynthID evaluation survives
at 99.97% TPR. Everything in this section describes that pipeline signature,
not watermark recovery; the measurement is in the empirical log of
[`synthid-detector-removal-plan.md`](synthid-detector-removal-plan.md).

`remove-ai-watermarks detect-synthid image.png --fixed-period` exposes the
legacy fixed-v2 diagnostic. It folds the image residual modulo 16x16 and
compares it with a frozen float64 template. It evaluates only native input,
without resize. Exact-multiple dimensions retain the original folding path;
non-divisible dimensions use count-correct modulo folding. The model and
threshold remain frozen from the 2048x2048 experiment. Through 10 megapixels,
the fixed threshold
accepted none of 5,000 public COCO views balanced across every observed target
geometry. A separate 5,000-view challenge used 256 generated geometries from one
through 18 megapixels and covered every pair of width/height remainders modulo
16; it also produced no accepted view. Later fresh-source challenges invalidated
that precision claim: fixed-v2 accepted 5/211 supported controls in one Open
Images cohort, and a proposed `0.28` threshold still accepted 1/213 in the
second. The branch is therefore diagnostic only and is never unioned into the
production positive route. The original 2048x2048 scores remain exactly
unchanged.

Above 10,000,000 through 18,000,000 decoded pixels, the production default selects
the separate `synthid-periodic-tile-large-v1` branch when both sides are at
least 2,048 pixels. It scores every phase-aligned 2,048-square window without
resizing. Every window must retain the combined template, Red-minus-Green, and
Blue-minus-Yellow spatial agreement; at least one window must also carry the
expected signed Blue-minus-Yellow mid-band phase. The 3072x5504 portrait alias
has an additional Green mid-band upper gate. The public score is the smallest
normalized gate margin and crosses at `1.0`.

The branch retained all 37 C2PA-inferred large candidates. Seven were then
submitted as metadata-free, decoded-pixel-identical files to Google's official
Gemini pixel verifier, and all seven were detected; an eighth submission was
indeterminate because the verifier quota ended. The final constants accepted
none of 17,417 exposed COCO, Open Images, and Spaces controls. After the
constants were frozen, the production path accepted none of a separate 2,637-
image feature-unseen local holdout: 2,000 previously excluded COCO images and
637 decoded-pixel-unique Picsum controls, balanced over four large geometries
and four resampling kernels. Its maximum score was `0.0592777965` against the
`1.0` boundary, giving a 95% zero-error upper bound of about 0.114% for that
holdout. The source collections predated the freeze and supported other
experiments, so this is not a fresh-acquisition estimate.

The slow post-freeze Open Images download supplied a separate source-fresh
audit. Excluding incomplete `.aria2` files, every prior Open Images decoded-
pixel hash, and duplicates left 41 complete controls from IDs frozen after the
large-v1 constants. The unchanged runtime accepted 0/41; the maximum score was
`0.4083013324`. This sample is too small to replace the 2,637-control interval,
but it independently checks the source boundary.

Codec robustness is outside that operating point. Re-encoding the same seven
official positives at their original dimensions as JPEG-95 or JPEG-90 reduced
the frozen large detector from 7/7 native detections to 0/7 for either quality.
The branch supports original or losslessly copied native pixels; a negative on
a lossy retranscode is explicitly inconclusive.

This geometry support does not imply arbitrary resize robustness. The fixed
carrier has a 16-pixel sampling lattice. In a stratified 80-image positive
sample, direct detection fell from 80 accepted originals to zero after each of
seven nonidentity resizes from 0.5 through 1.5. Scaling the template and folding
period to matching integers recovered the signal, and a conservative threshold
above 3,000 resized COCO development controls accepted 672 of 800 source-disjoint
provider positives with no acceptance in 2,000 final controls. That branch is
not shipped: noninteger periods from ordinary scale factors collapsed, and
less conservative per-period thresholds accepted five final controls. The
runtime therefore detects arbitrary decoded dimensions only when the carrier
retains its measured 16-pixel scale.

Through 10,000,000 decoded pixels, `remove-ai-watermarks detect-synthid
image.png` selects the registered-v3 detector by default. `--register-scale`
forces this branch even where the router would otherwise select large-v1. The
registered expert samples the 30 strongest
template harmonics over fractional periods, reconstructs the three strongest
canonical candidates, and combines full-frame correlation with quadrant and
three-level scale-space consistency. A positive result additionally requires
the canonical winner to be the strongest spectral candidate, a calibrated
threshold for its recovered period, and agreement in two independent
high-frequency template bands. Registered-v3 then confirms base crossings on
disjoint patch groups using origin-corrected harmonic phase, cyclic amplitude,
and a held-out unknown-codeword statistic. The reported score preserves the
base normalized margin only after confirmation; its threshold is `1.0`.

The final rule retained 229 of 355 source-disjoint transformed positives and
accepted none of 499 previously untouched Open Images controls. It retained
229 of 290 positives from scale 0.65 through 1.5, but none of 65 at scale 0.5.
A separate period-8 rescue was rejected because symmetric 0.5x control resizing
reproduced the same lattice and fully overlapped the positive feature range.
The measured input range is 250,000 through 10,000,000 decoded pixels.
Both dimensions must also be at least 256 pixels because the frozen positive
confirmation requires complete disjoint 256-pixel patch groups. Narrower
geometries need a separately calibrated adaptive-patch expert.

A later frozen 1,000-image Open Images reserve preserved zero registered
detections. Only 81 of those images were large enough for the fixed expert, and
seven crossed its standalone threshold. The two experts therefore must not be
combined with an OR rule: in their overlapping geometry, the registered gate
is the validated decision and a fixed-only crossing remains ambiguous. The
fixed expert is retained as a separately scoped carrier diagnostic, not as an
independent recall addition to registered mode.

Registered-v2 later accepted 4/2,997 supported controls in a source-fresh Open
Images test cohort. The frozen v3 confirmation rejected all four while retaining
147/148 base-accepted source-diverse positives and all 359 base-accepted views
in a dense 0.65-1.50 scale matrix. Without changing the rule, v3 then accepted
0/2,996 controls from a second nonoverlapping Open Images cohort and 0/2,366
supported controls from a 3,000-image COCO second-family challenge. The two Open
Images cohorts give a one-sided 95% zero-error false-positive upper bound of
about 0.050%. These results qualify a precision-first positive route, not an
absence verdict; the v2 sensitivity benchmark and scale-0.5 exclusion remain.

Those control rates are photographic. On 223 corpus images whose C2PA names a
non-Google generator, the unchanged production entry point accepted 29, a rate
of `0.130`, with `0.241` on Adobe Firefly and a highest foreign score of `3.01`
against the `1.0` threshold. Every acceptance came from registered-v3. The
lattice this branch reads is therefore shared across generation pipelines, and
the photographic upper bound above does not describe the rate a user meets on
AI-generated input. The branch is also phase-locked to the image origin: a
two-pixel diagonal crop killed all 28 in-geometry foreign detections and all 8
detected Google provenance positives, with the signal recovering only at
offsets that are multiples of four. A mark that survived cropping would not do
that; the route detects pipeline lattice on ordinary sizes as well as large
ones.

An exact runtime-parity check subsequently applied the recorded transform to
each of the 226 source-diverse assignments before invoking registered-v3. Two
half-scale outputs became too small for the research confirmation grid; 224
were scored. Registered-v3 detected 147/224 overall. All 40 supported 0.5x
views missed, while the measured 0.65x-1.5x range detected 147/184 (79.9%). The
unchanged registered-v2 base accepted 148 of those 184; v3 confirmation removed
only one true base crossing. The remaining sensitivity loss is therefore
period selection, amplitude, or high-band failure after resampling, not an
overly strict confirmation gate.

A preregistered same-image-null follow-up compares the selected carrier on the
two patch checkerboards with 16 neighboring periods from plus or minus 0.35 to
2.0 pixels. On two combined Open Images development cohorts, a near-threshold
base floor of 0.8, the existing frozen confirmation, and minimum joint
coherence excess `0.05695968150082637` rescued 7 of the 36 sub-threshold
0.65x-1.5x views. The frozen rule accepted none of the first 3,000 COCO
controls. It remains research-only until the untouched final control partition
and new positive parents pass unchanged. The final 2,000 COCO files contained
1,598 registered-supported images and seven near-threshold candidates. Four
candidates could not form the required two 256-pixel patch groups; the three
scored candidates had same-image excess at most zero. The frozen recovery rule
therefore accepted 0/1,598, as did registered-v3 itself. The negative-side gate
passed, but the lack of unseen positive parents still keeps the rescue outside
runtime.

Same-image contrast also failed to rescue spatial/spectral period mismatches.
Across the two 3,000-file Open Images cohorts, 469 controls passed the
preregistered mismatch prefilters and 212 passed frozen split confirmation.
Their maximum joint excess, `0.1762448251`, exceeded the `0.1464860382` maximum
of the five eligible transformed positive mismatches. The requirement that the
canonical and spectral period winners agree remains part of registered-v3.

A later content-adaptive research branch uses the registered tile only as a
synchronization basis. It standardizes every patch against all cyclic tile
shifts, chooses one phase on a checkerboard of selection patches, and confirms
the same phase on the disjoint checkerboard. A frozen joint standardized score
of `2.5`, combined with matching periods, the existing confirmation, both base
gate margins at least `0.45`, and one margin at least `1.0`, recovered 5 of 18
scored amplitude/high-band failures. It accepted none of 88 first-cohort gate
failures and none of 334 previously scored control candidates, but those are
development results. Its separately started Picsum feature-holdout then
accepted 0/350 decoded-pixel-unique controls unchanged. Only two controls
reached the mechanism pre-gates and their maximum joint patch-shift score was
`0.7029283` against `2.5`. The branch remains research-only pending unseen
positive parents. That check then failed: 21 resized views at 0.65, 0.70, and
0.75 from seven separate official pixel-positive large Gemini parents produced
0/21 registered-v3 detections and 0/21 patch-phase rescues. Their surviving
amplitude but inverted or weak RGB high-band response points to a different
carrier epoch or representation. The patch branch is not promoted; the next
test registers the separately measured large-v1 opponent-color signal.

The first opponent-color registration experiment then recovered 21/21 of
those views and selected the exact transformed period every time. It searches
7.5-14.5 pixels in the Red-minus-Green and Blue-minus-Yellow spectrum, then
requires fixed RGB, Red-minus-Green spatial, and Blue-minus-Yellow spatial
scores of at least `0.16`, `0.60`, and `0.55`. The same frozen candidate
accepted 0/21 symmetrically resized views from seven large Open Images
controls. The frozen candidate then accepted 0/350 decoded-pixel-unique Picsum
controls with a maximum decision margin of `0.7778322`.

The unrestricted branch was not production-safe. It accepted 605/2,997 and
587/2,996 controls from two wider Open Images cohorts; almost every crossing
selected the period-8 or period-12.8 codec lattice. It also accepted one of
3,964 COCO controls at period 10, below one megapixel, and 28/3,772
non-Google/non-OpenAI Spaces controls, all at period 8 or 12.8. Lossy
re-encoding destroyed the measured positive route: raw lossless resize retained
21/21 views at scales 0.5, 0.625, and 0.75, while JPEG-95, JPEG-85, and WebP-95
retained 0/63.

Those failures defined a narrower precision-first expert before a new control
holdout: 1-10 megapixels, both sides at least 768 pixels, and a selected period
from 8.1 through 12.0. It keeps the original three score thresholds and does
not require the strongest spectral alias to equal the spatially reranked
period. The latter restriction was removed after a public-API test showed that
it reduced the 0.55x cohort from 7/7 to 1/7 while the geometry gate already
excluded its only reserve control crossing. The final rule then accepted
0/1,000 untouched Picsum controls, with a maximum unrestricted decision margin
of `0.7953734`, and the production API detected 42/42 lossless views at scales
0.55 through 0.75 from the seven official-positive parents. It now ships as
`synthid-periodic-tile-opponent-registered-v1` after registered-v3 abstains.

A later period-8 codec-confound experiment extended that frozen expert without
mistaking the JPEG grid for a watermark. Half-scale lossless views retained 7/7
official positives at period 8, but ordinary JPEG controls produced the same
large template correlation. Their decoded opponent-color edge geometry was
different: every positive had both the Red-Green and Blue-Yellow native
8-pixel edge ratio at or below `1.05`. The threshold was selected against 600
development codec crossings, then rejected all 582 crossings in the held-out
Open Images cohort, all 601 in the feature-unseen frozen reserve, and all seven
in the heterogeneous Spaces challenge. Separately, 350 controls passed through
the same lossless 0.5x resize had no base carrier crossing. The runtime now
accepts periods 7.9-12.0 and applies this pixel-only veto through period 8.1.
The production API consequently detects 49/49 measured lossless views at scales
0.5-0.75 from the seven official-positive parents.

The same work did not recover lossy retranscodes. JPEG 4:2:0 creates a strong
inverted period-8 template in positives and natural controls alike. A
matched-transform 512-feature codec-residual discriminant accepted up to
86/525 holdout controls and did not generalize across positive parents. Eighty
block-DCT coherence variants also failed the precision-first gate: the best
zero-holdout-error statistic retained only 2/21 JPEG views. These are rejected
hypotheses, not hidden fallback branches.

The wider provider challenge produced a useful but non-attributive observation:
the unrestricted score accepted 95/7,254 OpenAI files with an explicit SynthID
provenance assertion, all at periods 10.70-10.80. It also accepted 4/287 OpenAI
lineage files without that assertion, including three in the production period
band. Missing assertion is not an oracle-negative watermark label, and the
feature does not identify a provider. All 95 decoded rasters were unique and
none overlapped the 94 hits from the earlier period-8 OpenAI candidate, so the
union covered 189/7,259 asserted files. The new component was nevertheless
codec-fragile: JPEG-95 and WebP-95 each reduced 95/95 native hits to 0/95.
It may be a complementary carrier epoch or an associated export/resampling
lattice; current labels cannot distinguish those causes. The local detector
therefore remains provider-neutral; OpenAI-wide coverage still comes from the
official pixel verifier.

Runtime routing now applies these policies directly and always abstains on
fixed-only evidence. The research bank in
`scripts/synthid_routed_expert_bank.py` still records fixed, registered, and
large observations separately for audits. No route claims absence because
encoder-version coverage remains incomplete.

Running the unchanged registered components directly above the declared range
did not justify a larger ceiling. From 10 to 18 megapixels it accepted 1 of 37
Google candidates and zero of 89 non-Google controls. High-band agreement, not
amplitude, was the main failure: only 3 of 37 positives cleared that gate.
Phase-aligned 2,048-square fixed-window consensus recovered 36 positives but
also accepted 10 controls by median score and eight when every window had to
pass. The natural and generator confounds are themselves spatially coherent.
Isotropic full-frame area reduction to one preregistered eight-megapixel target
also retained only 1 of 37 positives and zero controls; it was the same
4096-square native hit. Only three positives cleared high-band agreement after
the resize, so whole-image pre-resizing is not a large-image rescue.

The two remaining registered-window variants closed the registered large-image
branch.
One centered 2,048-square window retained 1 of 37 positives and zero of 89
controls. Accepting the best of every phase-aligned 2,048-square window retained
2 of 37 and zero controls, while the control maximum already reached 0.968
against the 1.0 threshold. This did not justify extending the registered
detector's 10-megapixel ceiling.

Three later checks did not change that boundary. Three near-10-megapixel aligned
windows per image retained 1 of 37 Google-labeled candidates and zero of 89
controls. A native fixed-window plus Green mid-band rule retained 15 of the 19
candidates in four recurring large geometries, but accepted one of 11,417
symmetrically resized Spaces controls and then retained none of those 19 after a
JPEG-90 re-encode. A JPEG-conjunctive period-16 codebook selected an RGB Green
mid-band direction on the pre-July split, retaining 23 of 26 candidates and zero
of 40 controls, but accepted 7 of 49 controls while retaining 10 of 11 candidates
on July. Lab and OKLab variants shared the same hard false positive. These
features are codec or renderer lattices, not robust large-image experts.

Those failures motivated the opponent-color branch documented above rather
than extending registered mode. The full 37-image cohort still has inferred
labels, so `37/37` is not an oracle recall estimate. The seven official Gemini
verdicts establish pixel-only positives at seven large geometries, but they are
still a small convenience sample. Three local records in the earlier 89-row
"control" set also crossed the final rule after decoded-pixel deduplication:
one is an Adobe file whose C2PA explicitly reports Google SynthID present, and
the other two remain pending official Gemini verdicts. They are not counted as
clean negatives.

A 64-pixel patch-consensus statistic for 0.5x inputs initially retained 33 of
49 validation positives and zero of 166 controls, followed by 27 of 52 locked
positives and zero of 140 controls. Its untouched broad challenge failed: 61 of
10,906 half-scaled Spaces controls and 22 of 1,000 half-scaled Open Images
controls crossed the frozen threshold. A post-challenge negative-Green spread
gate removed those false positives but retained only 2 of 234 later Google rows
and zero of 689 later controls. The result rejects patch consensus as a
half-scale runtime expert.

Two later rescue attempts did not improve that operating point. Trading
normalized amplitude against the minimum high-band correlation recovered 11
false negatives but accepted 19 of 11,506 symmetrically resized Spaces
controls. Using only the stronger high-frequency ring while vetoing balanced
broad-band matches also recovered 11 development false negatives and accepted
none of 499 reserve controls, but then accepted 13 of the 11,506 resized Spaces
controls. The respective full-corpus maxima exceeded their frozen thresholds.
Both forms measure general renderer or resize lattices and are rejected.

Projecting out the common 16-by-16 template and clustering the remaining tile
residual also failed the heterogeneous-control gate. A five-prototype codebook
retained 366 of 600 source-disjoint positives and accepted none of two separate
2,500-image natural-control splits, but accepted 828 of 11,506 metadata-labeled
non-Google Spaces controls. Its reproducible clusters occur across many image
generators and are not a SynthID-specific payload signature. Intersecting the
codebook with the registered min(R, B) carrier gate rescued none of the 138
remaining Google candidates. The codebook is not part of the detector.

Block-level spatial statistics did not make that codebook specific. Adjacent
carrier responses were more coherent in positives, but the best
development-selected block-dispersion feature retained only 11 of 60 reserve
positives and then accepted six of 1,000 fresh heterogeneous controls. A
threshold above the fresh-control maximum retained four of 120 pilot positives.
This spatial-payload branch is also excluded from runtime.

A separate geometry-stratified analysis found a second reproducible native
16-by-16 carrier. Independently fitted 1024-by-1024 miss templates correlated
at 0.869; independently fitted non-1024 miss templates correlated at 0.956 and
matched the 1024 template at 0.82-0.84, while matching the shipped carrier only
weakly. The signal also transferred across time: an early-only template
correlated 0.839 with a July-only template and retained five July misses.

The second carrier is not shipped. At arbitrary native geometries its first
frozen threshold accepted 25 of 11,506 heterogeneous controls. Requiring a
1024-by-1024 canonical view removed all 11,506 errors and retained 18 of 770
fixed-template Google misses, all originally 1024 by 1024. A two-template
consensus retained only three temporal misses. This initially established
repeatability within the Google cohort, but the external natural-image
challenge below shows that it is not specific enough to freeze a runtime
operating point.

The second carrier remained after projecting the shipped carrier out of every
normalized tile. Early and July orthogonal templates correlated at 0.834, the
early template retained five of 95 temporal misses, and its frozen operating
point accepted none of 81 reserve exact-geometry controls or 11,506
canonicalized heterogeneous controls. This supports an independent carrier
direction rather than a weak component of the shipped template, but does not yet
provide enough temporal positives for runtime calibration.

Mapping both scores over all 4,698 Google-labeled images found 3,825 first-only,
69 second-only, 103 both, and 701 neither cases. The scores correlated at
-0.563, and both directions occurred throughout the collection interval and
across multiple geometries. The second direction is therefore a coexisting
carrier state, not evidence of a dated replacement epoch. Its native threshold
is still unsafe outside exact 1024-by-1024 inputs: 8 of 11,506 heterogeneous
native controls crossed it. The zero-of-11,506 control result applies only to
the canonical exact-geometry challenge. A stricter threshold frozen above half
of those native controls had no crossing in the other half and retained 26
first-carrier misses, but the already inspected corpus cannot certify that
retrospective result.

A separate natural-image challenge rejected that stricter native threshold. It
accepted zero of 1,500 unique Open Images controls and zero of 12 Wikimedia
controls, but one of 637 content-deduplicated Picsum controls. Two apparent
Picsum crossings were byte-identical copies of the same image and count as one;
the collision still prevents a universal native operating point.

The original exact-1024 threshold also accepted four of 1,500 Open Images and
four of 637 unique Picsum controls, including native 1024-by-1024 images. A
previously defined consensus of two independent early templates still accepted
one Open Images and two unique Picsum controls while retaining three temporal
positives. Exact geometry and template consensus therefore do not make the
second direction specific enough for blind detection.

JPEG-95 agreement retained four of the five temporal positives but also all
eight external natural-image crossings at the original threshold. The confound
is transport-stable, so codec consensus does not rescue this branch.

The second direction is not a shifted or recolored copy of the first: its best
cyclic correlation was 0.212, its Fourier-magnitude correlation was 0.480, and
its strongest peaks were axial. A horizontal-axis-only ablation retained the
five temporal detections but accepted three of 11,506 canonicalized controls,
so the complete orthogonal template remains the more specific research feature.

A chronologically split low-rank subspace did not improve the second carrier.
The validation-selected rank retained two of 38 validation misses and four of
95 temporal-test misses with no error in its held-out control third. The
multi-state variant is rejected rather than selected from a better-looking
post-test rank.

No third stable linear carrier remained after deflating the first two. Early
and July residual averages correlated at 0.0003 and retained none of 95
temporal misses. The current linear periodic evidence supports two carrier
directions in the examined 1024-by-1024 corpus.

A positive-quadrant Euclidean norm in that two-carrier plane rescued no Google
image below both component thresholds and accepted one of 81 reserve
exact-geometry controls. Subthreshold component energy is therefore not
combined; each direction requires its own independently calibrated gate.

The five temporal positives at the original second-carrier threshold had much
more balanced normalized RGB contributions than seven of the eight native
control errors. A clean early-fit/early-validation split retained no validation
positive at its development-control threshold, however, even though it happened
to retain six later positives. Channel balance remains a post-test research
hypothesis and is not a detector gate.

A phase-only score then separated spectral phase from observed magnitude. Its
development threshold retained 10 of 95 July misses but accepted one of 81
reserve exact-geometry controls. Conjoining it with a separately calibrated
linear projection retained 1 of 31 early validation misses and 3 of 95 July
misses, with zero crossings among 162 heterogeneous exact-1024 controls, 1,500
unique Open Images, 637 unique Picsum images, and 12 Wikimedia images. The same
rule accepted three of 11,506 heterogeneous controls outside exact geometry.
This is a promising exact-1024 research candidate, but the temporal-positive
count is too small for runtime and the swapped-fit result below is not stable.

Across all 443 exact-1024 Google images, the candidate added 11 detections that
the shipped carrier missed and overlapped it on 16; 244 were found only by the
shipped carrier and 172 by neither.

Swapping the early fit halves and recalibrating both gates retained four of 31
opposite-half validation misses and four of 95 July misses, again with no
conjunction crossing among 81 reserve exact-geometry controls. The swapped
operating point then accepted one of 92 unique exact-1024 Open Images controls,
though none of 637 unique exact-1024 Picsum controls. Fit-split signal
repeatability does not yet provide a stable operating point.

An initial two-expert rule accepted none of a newly collected 100-image native
exact-1024 Open Images block and appeared to add five of 443 Google files,
including two of 95 July misses. A later content audit found three exact
decoded-pixel duplicate pairs and ten near-duplicate groups in the 443 files.
One early near-duplicate pair had been split between the two expert fits, which
invalidated the apparent independence and the five/two recall result.

Refitting after allocating whole content groups to one side retained six Google
files and added only two files missed by the shipped carrier, including one of
95 July misses. Its conjunction accepted none of 81 reserve exact-geometry
controls, 92 exact-1024 Open Images, 637 exact-1024 Picsum images, or the 100
new Open Images controls. At arbitrary native geometries, however, the two
corrected experts accepted 5 and 6 of 11,506 heterogeneous controls and their
conjunction still accepted 2. Both consensus errors were outside 1024 by 1024.
The result remains research-only and does not generalize into a universal-size
second-carrier detector.

A stricter post-hoc joint margin above both arbitrary-size control collisions
retained the two corrected incremental exact-1024 positives. Across all 4,698
Google files it accepted 28 and added 16 files missed by the shipped carrier in
11 geometries. All 16 belonged to separate perceptual content groups with no
shipped-positive sibling. It accepted none of 1,500 Open Images, 637 unique
Picsum, or 12 Wikimedia native views. This is an all-size research hypothesis,
not validation: the margin used the complete 11,506-control result, and the
natural corpora had already been exposed to related experts. A new
content-deduplicated AI-control corpus is required before implementation.

A source-independent public model cohort gave the original group-separated
conjunction 2 of 589 Gemini 3.1 Flash Image Preview images, zero of 520 Nano
Banana Pro Preview, and zero of 280 DALL-E 3 images. The two Gemini hits were
visually distinct diverse images at 1408 by 768; the cohorts also included
solid-color and gradient probes. The post-hoc strict margin accepted none: the
family maxima were 1.011 and 0.941 against its 1.033 boundary, while DALL-E 3
reached 0.514. Thus the base rule has weak current-Gemini transfer but retains
the two arbitrary-size control collisions, while the strict rule removes both
through a post-test threshold. Neither is a validated universal current-Google
or cross-provider SynthID signature.

Three perceptually matched pairs contained one shipped-carrier crossing and one
non-crossing variant. In all three, the matched difference reduced the shipped
template while increasing both corrected second-template directions. This is
mechanistic support for coexisting carrier states, but three pairs give a
two-sided sign-test result of 0.25 and do not validate a detector.

All three temporal detections from the original first-expert rule survived JPEG
95, 85, and 70, but none survived
WebP 95 or a 0.75x down-and-up resize round trip. A symmetric challenge found
one JPEG-85 crossing among 162 heterogeneous exact-1024 controls, while 92
exact-1024 Open Images and 637 unique exact-1024 Picsum controls stayed below
threshold in every view. That transform result applies only to the first-expert
rule. The corrected group-separated experts have not been transport-calibrated;
no JPEG claim transfers to them.

A later causal test used all 16 strict incremental hits available at that
stage. Subtracting the normalized sum of the two content-group-separated
expert directions cleared every linear and phase component on all 16 images;
the same amplitude with a one-pixel cyclic shift cleared none. Median fidelity
was 63.86 dB PSNR and 0.99989 SSIM, with minima of 58.92 dB and 0.99961. The
source carrier was fragile under transform: only one source remained strict at
JPEG 95 and 90, and aligned suppression cleared that one in both views. This is
strong local evidence that the second score follows a real pixel carrier, but
not evidence that it is a robust or provider-specific watermark.

Joint suppression was then tested on all 28 strict second-carrier hits. The
first carrier was suppressed only when present, followed by the second carrier.
The result left zero first-carrier and zero second-carrier survivors; neither
edit reactivated the other direction. Median fidelity was 61.69 dB PSNR and
0.99984 SSIM, with minima of 58.15 dB and 0.99910. Shifted controls left one
first-carrier and seven strict second-carrier survivors rather than reproducing
the aligned result. Together with the failed third-carrier fit, this exhausts
the current linear native 16-by-16 Google hypothesis as two jointly controllable
states. It still does not replace a matching-provider oracle result.

The bounded search is materially slower, but registered-v3 is now the default
ordinary-size route because fixed-v2 failed its fresh-source precision gate.
Registered-v3 itself does not reliably detect 0.5x carriers. The later bounded
opponent fallback covers the measured lossless 0.5x case with its codec-grid
veto, but does not make the detector universal across crop, codecs, carrier
states, or providers.

A crop-specific follow-up tested cube-root LMS and OKLab projections, all six
DTCWT orientations, and explicit FFT phase-lock metrics after period-and-phase
registration. Each representation exposed additional positive signal, but its
development-selected candidate failed a fresh control challenge. The strongest
registered green-channel phase candidate accepted five of 1,000 COCO controls;
a threshold above their maximum retained only eight of 100 positives. These
features remain research diagnostics and are not part of the runtime detector.
See the
[`Registered color and phase-lock challenge`](synthid-detector-removal-plan.md#2026-08-12-registered-color-and-phase-lock-challenge).

Green-channel inversion of the 32 strongest conjugate carrier pairs then
cleared 58 of 59 locally detected public positives while preserving at least
43.36 dB PSNR and 0.99048 SSIM. This demonstrates precise control over the
local periodic correlate, not the proprietary decoder. A fixed Google-oracle
challenge made that distinction explicit: all three phase candidates cleared
the local threshold at 55.41-57.86 dB PSNR, while Gemini still reported Google
AI signals for all three. The recoverable source controls and RMS-matched shams
were also positive. One of nine submitted chats did not persist, but every
phase candidate produced a verdict. Blind Green-channel SWT-HH thresholding
cleared none of the 59 local positives. See the
[`Green phase perturbation and blind SWT removal`](synthid-detector-removal-plan.md#2026-08-12-green-phase-perturbation-and-blind-swt-removal)
challenge.

Those three oracle-confirmed phase candidates are now adversarial hard
positives: both the native and registered runtime modes miss all three. A
phase-invariant Blue-carrier magnitude rescue recovered all three and happened
to reject 3,000 COCO controls when combined with a native-score floor, but it
then accepted 90 of 11,506 metadata-labeled non-Google controls. The branch is
therefore a shared generator or renderer correlate, not a SynthID-specific
rescue, and is not included in runtime.

A public `cebeuq/Synthid-Bypass` V2 corpus supplied a separate external check.
The native detector accepted 10 of 12 `before` images and none of the 12
diffusion-reconstructed `after` images. Gemini Verify AI independently reported
SynthID on both missed sources `03.webp` and `07.png`, and no SynthID on their
paired outputs. It also reported no SynthID on outputs `01` through `06`; the
daily verifier limit prevented completing `08` through `12` in the same
session.

A separate audit of the later `aloshdenny/reverse-SynthID` V4 codebook
reproduced its published phase score without executing third-party code or
pickle payloads. The bundled positive sample crossed its `0.52` threshold, but
the same detector accepted 141 of 355 Google positives, 191 of 499 controls,
and 386 of a later 1,000-image Open Images reserve. Its paired-corpus AUC was
0.517. The stricter 0.3%-aspect-ratio router still detected 132 of 343 supported
controls and 284 of 685 supported fresh controls. The older V3 dark/white phase
score had AUC 0.473 and, at its documented 0.78 phase threshold, accepted 5 of
355 positives, 5 of 499 controls, and 6 of 1,000 fresh controls. Neither
external operating point is part of runtime. Prespecified amplitude-aware
reranking within a 4-128-pixel carrier band also failed, with best-of-model AUC
at most 0.524.

An exact-1024 rerun of the numeric V4 artifact provided a direct confirmation.
Its Gemini 3.1 profile accepted 117 of 443 Google rows and 28 of 162 controls;
the Nano Banana profile accepted 92 and 39, and their union accepted 177 and
60. This is the same nonspecific operating point on a cleanly bounded geometry,
not a missing resolution route.

The useful finding is narrower: truly flat Gemini references have widespread
cross-image phase coherence, so cross-color consensus remains a valid discovery
tool. The published DALL-E 3 `black` and `white` folders do not provide the same
OpenAI experiment. Their image means vary widely and only 39 and 32 RGB bins
respectively exceed 0.9 phase coherence across ten 1024-square images, compared
with 20,443 and 100,252 for the corresponding Gemini 3.1 buckets. Only four
bins crossed 0.9 in both DALL-E color cohorts, all at trivial DC or
self-conjugate-axis coordinates. These are heterogeneous content examples, not
solid OpenAI references, and cannot calibrate an OpenAI pixel detector. More
fundamentally, the official SynthID-Image paper says nearly uniform corner cases
may be excluded from watermarking. A flat output is therefore not automatically
a stronger or even positive watermark reference.

A later exact-geometry challenge used 1,124/579/562 train/validation/test
OpenAI-asserted images at 1086x1448 and 399/203/228 same-size general controls.
A 256-bin polarity-invariant phase codebook learned from the lowest-texture
train images was not reproducible: deterministic train halves shared only two
exact bins. Native test AUC was 0.512 and JPEG-95 test AUC was 0.512. The
zero-validation-control threshold accepted none of 562 test positives; a 1%
validation-FPR threshold accepted four positives and two controls. This rejects
the hypothesis that low texture reveals one shared OpenAI absolute phase.

Testing the paper's content-dependent mechanism directly also failed to produce
a stable expert. A 60-feature OKLab model measured only within-image alignment
between blockwise residual energy and local texture, contrast, and chroma, with
no global phase or amplitude. Its native/JPEG minimum reached test AUC 0.593 and
accepted 15 of 562 OpenAI rows versus one of 228 controls at the frozen
validation boundary. Independent train halves had coefficient cosine 0.148;
one accepted 13 positives and two controls while the other accepted none, with
no overlapping positive. This is an unstable content or export correlate, not
a detector.

The same assertion-contrast method was then applied to the exact 1254-square
cohort. Validation selected an sRGB period-8 Blue-channel candidate at 45 of
259 asserted rows and zero of 16 same- or other-provider rows. Its locked test
accepted 39 of 233 asserted rows and one of 18 controls. Across all 992 asserted
rows at that geometry it accepted 185, alongside one of 55 same-provider rows
without an assertion and one of 13 other-provider rows. A threshold raised
after those errors retained only a small minority of positives and cannot be
called a new codeword. This geometry-specific branch is rejected.

The two misses expose different boundaries. `07.png` contains the usual
positive carrier at low amplitude: its fixed score is `0.12484`, Green is the
strongest signed channel, and all nine aligned spatial regions are positive.
Lowering the threshold or adding that channel-and-spatial conjunction is not
safe. A fresh, source-verified 1024-by-1024 Open Images photograph scored
`0.21237`, had an even stronger Green-dominant and nine-region response, and
Gemini reported `SynthID not detected`. The current runtime therefore has a
confirmed natural-image false positive outside the corpora used to freeze its
threshold. Separately, Lanczos-resized natural Kodak PNGs reached `0.37683`,
showing that some rational resampling lattices can imitate the signed carrier
even inside the challenged pixel-count range. The earlier zero-of-5,000 COCO
results remain true for those exact transformations, but they do not establish
universal specificity.

`03.webp` is not recovered by the two group-separated alternate-Gemini experts.
Instead it has a spatially uniform opposite-polarity response: fixed correlation
`-0.32634`, all RGB channel correlations below `-0.28`, and all nine aligned
regions negative. Its oracle-negative paired output weakens to `-0.15314`.
No image crossed `-0.20` in either 5,000-view COCO geometry challenge or in the
fresh natural-image blocks, but 40 of 11,506 heterogeneous non-Google-labeled AI
controls did. Those crossings include multiple generator families, so the
negative direction is a plausible additional codeword or shared renderer state,
not a provider-specific detector. Both hard positives remain research cases;
neither a lower positive threshold nor an inverse-template branch is shipped.

Separating signed channel correlations produced a more specific research
candidate. The three oracle-confirmed Green-phase hard positives retained Red
correlations of 0.781-0.804 while their Green correlations became negative. A
frozen `Red >= 0.377 and Green < 0` conjunction accepted all three and none of
15,005 controls across three independent corpora. It recovered 19 of
58 synthetic Green inversions that cleared the native detector. This remains
research-only because the rule was motivated after inspecting the attack,
only three recovered images have external oracle labels, and no untouched
control corpus remains for a final challenge.

A registered transform challenge exposed one false positive among 3,000 COCO
controls when the Red-only rule searched all 256 phase offsets. Searching six
fixed carrier periods added no further false positives. A stricter candidate,
already frozen before that result, requires both unchanged color channels:
`min(Red, Blue) >= 0.377` and `Green < 0`. It accepted none of the 3,000
controls after either phase-only or phase-and-period registration; the largest
registered control score was 0.342. It also accepted none of 1,200 transformed
views made from 100 fixed Open Images controls, whose largest score was 0.332.

On the three oracle-confirmed hard positives, the stricter rule retained all
three at native scale and after three crops. Six-period registration retained
all three after 0.65x, 0.75x, 1.25x, and 1.5x resizing. It retained none after
0.5x resizing or JPEG round trips at quality 95, 85, or 70. All corresponding
source and RMS-noise sham views remained negative. This is evidence for a
bounded phase-and-scale rescue, not arbitrary-resolution or codec robustness.

A later five-period challenge over all 11,506 metadata-labeled non-Google
controls invalidated the common 0.377 threshold: it accepted 16 controls, two
at period 20 and 14 at period 24, with a maximum score of 0.435813. A
conservative threshold strictly above that maximum retained all three hard
positives from 0.75x through 1.5x, and accepted none of the same 11,506 controls
after symmetric 0.75x, 1.25x, or 1.5x resize round trips. The control maxima
were 0.431352, 0.393949, and 0.372036.

At 0.65x, the symmetric control maximum of 0.397396 exceeded the weakest hard
positive at 0.394911. An exploratory period-10.4 gate added
`Blue >= 1.1 * Red` to the original R/B and negative-G conjunction. It retained
all three hard positives while the largest qualifying score among all 11,506
controls was 0.355165 natively and 0.354955 after the same 0.65x round trip.
The combined candidate retains all three hard positives after identity, three
crops, and resizing from 0.65x through 1.5x, while rejecting their source and
noise-sham counterparts.

Sensitivity remained narrow on the broader synthetic attack cohort. Of 58
Green inversions that cleared the native detector, the combined rule recovered
4 at 0.65x, 5 at 0.75x, 16 at identity, 11 at 1.25x, and 10 at 1.5x. The three
oracle source images are included in that cohort, and only one additional
synthetic source passed at 0.65x. This is a high-specificity residual-carrier
rescue, not a universal phase-attack detector.

A source-split Fisher projection of the three channel correlations did not
improve the tradeoff. Period-specific thresholds fitted on 5,719 training
controls accepted 11 of 23,148 views from 5,787 test controls, while recovering
only 4 of 28 scale views from seven source-held-out attacks. The learned linear
branch is rejected.

Aligned 2x2 and 4x4 spatial-consistency grids also failed to improve the 0.65x
frontier. Across all 537 controls with global scores at or above 0.20, local
R/B strength, negative-G coverage, and `Blue / Red` coverage all overlapped the
58 synthetic detector misses. The best zero-control conjunction still
recovered only four attacks; a five-attack rule accepted two controls. The
spatial branch is rejected.

The same three attack-derived positives still provide all external oracle
labels, the 0.65x ratio was selected after observing a control collision, and
the conservative threshold came from an already exposed corpus. The branch
therefore remains outside runtime pending new preregistered oracle positives
and an untouched control challenge.

An exploratory attempt to rescue JPEG and 0.5x cases by adding the magnitude
of negative Green correlation to the R/B score did not improve this boundary.
Transform-wide calibration raised the safe thresholds to 0.655-0.695; both
discordance metrics still retained no JPEG case and only one of three 0.5x
cases, matching a relaxed R/B-only score. They are rejected as redundant.

Three further attempts did not extend that boundary. JPEG-specific templates
learned from 50 other public positives recovered none of the nine JPEG hard
positive views and accepted two to three of 150 evaluation controls. A frozen
low-to-middle radial band did retain all three hard positives after JPEG 95,
85, and 70, but phase search accepted 179 of 12,000 COCO views. Adding
four-quadrant consistency still accepted 189 of 34,518 views from 11,506
metadata-labeled non-Google controls, including camera images. Removing phase
search did not solve the confound: the fixed-phase band accepted 248 of 12,000
COCO views, whose maximum score exceeded every hard positive. The
JPEG-surviving component is therefore a general low-frequency or codec lattice,
not a SynthID-specific rescue.

For 0.5x inputs, a physically reduced 8x8 template was tested after projecting
the shared 2x2 lattice out of both template and observation. A threshold above
all 11,506 symmetrically downscaled controls was 0.396, while the three hard
positives scored only 0.277-0.288. Channel separation therefore does not rescue
the already rejected period-8 branch.

An untouched 2026-08-07 through 2026-08-10 temporal cohort then challenged the
runtime detector without refitting its template or threshold. After correcting
the evaluation cohorts for mixed-provider provenance, native detection accepted
183 of 252 files with an explicit Google LLC SynthID assertion and 3 of 488 with
an explicit OpenAI-only assertion. Scale registration accepted 130 and 1,
respectively. Among 170 files with no SynthID provenance assertion, the native
and registered modes accepted eight and two. These are not oracle-negative
labels, so they bound operational specificity without establishing it.

The same frozen native detector retained 153 of 252 explicit-Google files after
a symmetric 0.75x resize round trip, 66 after JPEG-95, and 54 after WebP-95. A
5% center-crop round trip retained none. The temporal result confirms a real,
partly codec-tolerant Google pixel signal across many sizes, but also confirms
that the current fixed-phase statistic is not a universal SynthID decoder.
Applying the already frozen scale-registration path after the same crop
recovered only 8 of 252 explicit-Google files while accepting none of 488
explicit OpenAI-only files. Crop robustness therefore needs a different,
independently calibrated phase-and-support model; enabling the existing scale
search is not a fix.

A diagnostic joint transform explains part of the failure. Undoing the known
0.95 crop scale and scoring the tile at the cyclic phase predicted from the
removed border reached 0.859 AUC against every other temporal cohort. A
post-hoc threshold above all 671 non-Google rows retained 37 of 252
explicit-Google files. Searching all 256 phases was weaker at 0.839 AUC and
retained 41. The geometry-predicted phase is therefore a plausible crop
mechanism, but its threshold has observed the temporal controls and cannot enter
runtime until a new future holdout confirms it.

A positive result identifies the carrier but does not attribute a provider.
Provider identity still comes from provenance.

The command reports `indeterminate` separately from `unsupported`. Both are
inconclusive: the first means no qualified local expert crossed its threshold,
and the second means no local expert covers the geometry.

The same modulo-folding method has been tested separately on a large,
temporally split OpenAI-labeled corpus. Its strongest native-size template was
dominated by a generic 2x2 generator lattice that also appeared in multiple
non-OpenAI controls. Removing that nuisance component left a sparse,
time-limited signal with inadequate sensitivity. OpenAI pixel detection is
therefore not part of the runtime expert.

Learned residual, forensic, ensemble, and canonical 512x512 representations
were also tested against 261 same-provider candidate controls. A later
software-agent audit found that only 118 of those controls explicitly name
`gpt-image 2.0`; the rest come from earlier or unknown versions. The strongest
native ensemble accepted 243 of 1,364 development-test positives with no
accepted controls, but accepted none of those positives after a JPEG-95 round
trip. A model trained after equalizing every image through JPEG-95 accepted
only six development-test positives and five COCO controls. The apparent
native signal is therefore treated as an export noiseprint rather than a
validated robust watermark. A local CLIP search over the exact-version subset
found no clean same-content before/after pair, and a published third-party CNN
surrogate mislabeled 83.4% of held-out COCO controls at its stated threshold.
A transform-augmented 512x512 RGB-plus-residual CNN then accepted zero of 1,364
development-test positives in native, JPEG-95, and resize views; its crop view
accepted one positive and one difficult control. Detailed counts and rejected
alternatives are in
the [`OpenAI periodic-carrier challenge`](synthid-detector-removal-plan.md#2026-08-10-openai-periodic-carrier-challenge)
and [`OpenAI content-dependent decoder challenge`](synthid-detector-removal-plan.md#2026-08-10-openai-content-dependent-decoder-challenge).

A later opponent-color screen found a narrower OpenAI pixel candidate that the
RGB experiments had not tested. Across 75 color-space, period, and channel
variants selected on validation only, the winner was the third cube-root LMS
component at period 8. It required the same image to clear independently fitted
native and JPEG-95 thresholds above all validation controls. On the locked test
it accepted 16 of 158 OpenAI images and none of 135 heterogeneous controls.
Those 16 spanned 11 collection dates and all three native geometries, and none
shared a perceptual-hash group across splits.

The signal is not merely the old 2x2/4x4 export lattice. Although 84-90% of the
raw period-8 template energy projected onto a period-2 or period-4 subspace,
subtracting the complete period-4 projection before refitting still accepted
15 of 158 test positives and none of 135 controls. The frozen candidate
retained all 16 source detections after WebP-95 and four after JPEG-90, but none
after crop or resize round trips. Exhaustive cyclic phase registration did not
rescue those geometric transforms. Among 52 action-derived same-provider
OpenAI controls it accepted one, and none of the 12 controls explicitly naming
`gpt-image 2.0`; those counts remain far too small for provider specificity.

A direct pixel ablation supplied local causal evidence. Subtracting the frozen
period-8 direction from only the sRGB Blue channel cleared both native and
JPEG-95 scores on all 16 sources, while the least-correlated cyclic shift
cleared none. Median amplitude was two Blue levels, with median 52.24 dB PSNR
and 0.99639 SSIM; the worst case fell to 40.62 dB and 0.97184. This controls the
local score but is not an OpenAI-oracle removal result.

The candidate does not make OpenAI detection universal. A frozen all-size map
accepted 94 of all 7,259 OpenAI-labeled images and 9 of 8,670 heterogeneous
controls. The three training geometries supplied 76 of those 94 positives,
while the common 1086x1448, 1254x1254, and 1122x1402 exports supplied none.
A preregistered search over integer periods 4 through 16, calibrated above the
maximum period-searched validation control, retained 14 of 1,839 test OpenAI
images and one of 2,162 test controls. Every accepted positive selected period
8; no scaled period added a detection. The measured feature is therefore a
real, codec-tolerant, raster-phase carrier candidate in a narrow native subset,
not a universal OpenAI SynthID detector. Its attribution still requires an
authorized OpenAI oracle or adequate same-model oracle-negative pairs.

A phase-free follow-up tested whether geometric resampling destroys carrier
phase but leaves a usable spectral envelope. It fitted LMS periodic magnitude,
power, and log-magnitude profiles at periods 4 through 16 and required native,
JPEG-95, and 0.75x-resize agreement. The validation-selected period-16 power
ensemble accepted 8 of 158 native-geometry test positives and none of 135
controls. Without refitting, it also accepted none of 4,389 wider Spaces
validation/test controls and none of 118 exact-version same-provider controls;
one of all 261 mixed-version same-provider candidates crossed. Five of the
eight detections overlapped the signed period-8 carrier and three were new.

This does not supply an independent universal expert. Removing exact period-8
Fourier support left five test positives but admitted two of 135 controls;
removing the broader period-4 support removed all test positives. A stronger
requirement that one period-15 magnitude template serve native, JPEG, and
resize views looked promising on native geometries, then accepted 14 of 2,162
wide test controls and two of 118 exact-version same-provider controls. The
safe period-16 result instead uses three separately fitted view templates, whose
native and resize directions correlate only 0.061. It is a transport-consensus
diagnostic of the same harmonic family, not a single resampling-invariant
codebook and not a runtime detector.

A final scale-covariance test evaluated the proposed fractal interpretation
without fitting any provider template. It compared each image's phase-free LMS
spectrum with its own JPEG-95 spectrum and with a physically reduced 0.75x
view, scaling candidate periods from 8, 12, 16, 20, and 24 accordingly. The
best validation choice retained three positives, then accepted zero of 158
locked-test OpenAI images and one of 135 controls. Median self-similarity was
lower for OpenAI than for controls. Simple spectral fractal or scale-covariant
self-similarity is rejected.

Higher-order phase coupling did not rescue the fractal interpretation for
Gemini. A block-bicoherence probe used period-16 harmonic triplets whose
combined phase is mathematically invariant to global translation. Seventy-two
Green, cube-root LMS, OKLab, residual-scale, block-size, and harmonic-count
variants were charged to separate fit and selection splits, followed by an
independent control calibration. The selected variant accepted none of 20
selection positives. Its untouched result was 0 of 50 Gemini positives and 0
of 199 controls, with AUC 0.374. The known Gemini signal is not a detectable
multiscale harmonic cascade in this representation.

The common export sizes were then tested explicitly rather than treated as
unknown arbitrary geometries. For the dominant 1086x1448 cohort, an isotropic
inverse mapping to the plausible 1536x2048 source raster recovered none of 579
validation or 562 test positives. Direct fractional registration at the
corresponding approximately 5.66-pixel output period retained only 4 of 562
test positives and accepted 2 of 135 controls; the median OpenAI score was
lower than the control median. The candidate is not hidden at a simple
`1/sqrt(2)`-scaled period.

Nonlinear tests also failed the specificity boundary. Folding the magnitude,
energy, normalized energy, and cross-channel products of LMS and OKLab
residuals selected a period-4 absolute LMS residual. It retained 43 of 158
native-geometry test positives but accepted 2 of 135 controls. On the frozen
wide challenge it accepted 52 of 1,839 test OpenAI images, 5 of 2,162 test
Spaces controls, and 10 of 261 action-derived same-provider controls, including
5 of 118 explicit `gpt-image 2.0` controls. Four-quadrant patch consistency
retained 41 positives without removing the two native-geometry control errors.
A separate 360-candidate lag-product screen selected a period-16 vertical-lag
feature and retained 43 positives, but accepted four controls.

The current manual OpenAI search is therefore bounded rather than successful.
Signed phase, phase-free power, subperiod deflation, scale and inverse-raster
registration, spectral self-similarity, nonlinear periodic variance, patch
consistency, and lag autocorrelation either have low recall or fail held-out
specificity. These features remain research measurements of renderer structure;
none is a runtime OpenAI SynthID detector. Further feature selection needs
provider-authorized oracle labels or clean same-content counterfactual pairs
and a fresh temporal holdout.

That temporal holdout is now available for validation, but it did not rescue the
OpenAI claim. The untouched 2026-08-07 through 2026-08-10 cohort contained 486
explicit OpenAI-provenance positives, 504 heterogeneous controls, and only seven
pure OpenAI C2PA files without a SynthID assertion. The frozen signed period-8,
phase-free period-16, and nonlinear period-4 candidates accepted 5 of 486, 2 of
40 supported geometries, and 14 of 486 positives, respectively. Their control
counts were 1 of 504, 1 of 50 supported geometries, and 8 of 504. None transfers
as an OpenAI SynthID detector.

The previously frozen 512-square full-image forensic model transferred better:
82 of 486 positives crossed its unchanged threshold, against one of 504 general
controls and one of seven pure OpenAI C2PA candidate controls. Its positive
scores separated strongly in aggregate, but all 82 native detections disappeared
after both JPEG-95 and WebP-95 round trips. Resize retained 46 and crop retained
23. This temporal and transformation result supports the existing export-
noiseprint interpretation rather than watermark attribution. Further adaptive
feature selection on the same corpus is not justified without provider-oracle
labels or clean counterfactual pairs.

A provider-key hypothesis was tested explicitly rather than assuming that
OpenAI and Google share one fixed template. Spherical clustering fitted up to
32 period-8 cube-root-LMS carrier directions on OpenAI training images, with
cluster count selected on validation only. Eight directions increased the
native-geometry development-test count from 16 to 27 of 158, but accepted one
of 135 heterogeneous controls and two of 52 action-derived same-provider
controls. The two dominant directions contained 234 of 283 training images and
correlated at 0.982 natively and 0.924 after JPEG; they are not independent
codewords.

A complete provider challenge clarified the confound. The frozen eight-
direction model accepted none of 443 Google files, but accepted 5 of 39
Microsoft Designer files and 123 of 674 OpenAI-platform files. Every Microsoft
hit had joint `Microsoft, OpenAI` provenance, one explicitly asserted an OpenAI
SynthID watermark, and all five selected the same dominant direction as 111 of
the 123 OpenAI hits. On the August temporal native-
geometry cohort it accepted five unique OpenAI content groups and two Microsoft
groups after SHA-256 deduplication. A sign-invariant carrier-subspace model
retained only 1 of 158 development-test positives and none of 40 fresh rows.
After fitting an OpenAI direction orthogonal to the Google, Microsoft, and
other-provider training means, only 1 of 158 development-test positives and
none of 40 fresh rows remained.

Regrouping by the signed watermark assertion makes the interpretation narrower
but not purely negative. The model accepted 115 of 589 files explicitly
asserting an OpenAI SynthID watermark, 13 of 117 files with OpenAI lineage but
no watermark assertion, none of 443 Google files, and one of 89 other-provider
files. Aggregate enrichment over OpenAI lineage without an assertion was
significant by a one-sided exact test (`p = 0.0179`), but it was not
independently significant in the already exposed development-test split
(`27/159` versus `2/25`, `p = 0.202`). Missing C2PA action is not an
oracle-negative watermark label, so either attribution remains provisional.

The frozen multi-direction score had more codec persistence than the rejected
full-image noiseprint. Of 27 native development-test detections, WebP-95
retained 24 and added nine other positives; JPEG-90 retained eight and added
none. The corresponding control counts were one of 135 under WebP and zero
under JPEG. A 0.75x resize and 5% crop retained none. The best current
interpretation is a real raster-phase component associated with the
OpenAI/Microsoft lineage and distinct from the measured Google carrier. It may
be one projection of a provider-keyed watermark family, but it is neither the
complete robust SynthID surface nor a universal OpenAI detector.

The provider-specific-code hypothesis is architecturally plausible but has two
different forms. The SynthID-Image paper explicitly separates binary watermark
detection from payload recovery, describes payloads as a way to distinguish
customers of the same service, and makes the encoder determine the watermark
version. Different providers can therefore use one SynthID family without
sharing encoder versions, payloads, or observable carrier templates. This does
not imply that provider identity is a fixed FFT phase offset: the encoder and
payload are content-dependent and the detector can be updated across multiple
encoder versions.

A direct carrier-family comparison rejected the narrowest form of that
hypothesis. It compared 581 byte-unique OpenAI-asserted images, 443 Google-
asserted images, 93 OpenAI-lineage images without a watermark assertion, and 82
other-provider controls. In period-8 cube-root LMS residuals, the signed phase
and phase-free power contrasts were stable between deterministic cohort halves:
OpenAI stability was 0.949 and 0.957, while Google stability was 0.779 and
0.877. Raw cross-provider power had cosine 0.480, consistent with common image
and export structure. After subtracting the respective control means, however,
positive power support had cosine 0.0123, a bootstrap median of 0.0232 with a
95% interval of 0.0009 to 0.0856, zero overlap among the 12 strongest
coordinates, and per-channel cosines of 0.0085 to 0.0155. Signed cross-provider
contrasts were negative rather than phase-locked. The measured OpenAI and
Google components are therefore not one fixed frequency support carrying two
different phases. They remain compatible with distinct SynthID encoder
versions or content-dependent nonlinear codes, which require separate learned
experts and provider-oracle validation.

A frozen, non-adaptive check with OpenAI's public verifier then resolved the
most important attribution question. One C2PA-asserted image accepted by the
eight-direction period-8 candidate was checked both as its original PNG and as
a newly encoded pixel-identical PNG. OpenAI Verify reported `SynthID detected`
and `Content Credentials not detected` for both files. The local component
therefore overlaps a genuine OpenAI SynthID watermark rather than relying on
metadata. A second asserted OpenAI image that the local candidate rejected at
native/JPEG scores 0.709/0.657, below its 0.918/0.923 thresholds, was also
re-encoded without metadata. The oracle again reported `SynthID detected` and
`Content Credentials not detected`. This is direct evidence that the current
period-8 model is one real but incomplete OpenAI SynthID expert, not a universal
decoder. The oracle check stopped after these preselected validation cases;
OpenAI's Content Provenance documentation explicitly disallows repeated
queries to reverse-engineer, remove, or evade a watermark.

Per-direction calibration does not safely recover that false negative. Giving
each of the eight directions its own threshold above the corresponding
validation-control maximum raised validation recall to 36 of 140 with zero of
145 controls, then accepted 46 of 158 locked-test OpenAI rows and 4 of 135
controls. On the wider provider challenge it accepted 180 of 603 explicit
OpenAI-SynthID rows, 15 of 80 OpenAI-lineage rows without an assertion, 6 of
443 Google rows, and 7 of 112 other-provider rows. Fresh temporal counts were
13 of 40 OpenAI rows, 4 of 50 general controls, and 1 of 3 same-provider
controls. The oracle-positive false negative selected direction 4, but that
direction retained only 1 of 4 positives under leave-one-positive-out refits;
the oracle-positive row then failed its JPEG threshold. The weak directions
are unstable clusters, not defensible additional codewords.

A complementary train-only bilinear probe looked for carrier directions whose
within-image variation remains correlated between native pixels and a JPEG-95
round trip. It selected a rank-1 positive covariance contrast on validation and
accepted only 1 of 158 locked-test OpenAI rows, zero of 135 controls, zero of
40 fresh OpenAI rows, and zero of 53 fresh controls. Variable payload phase is
therefore not recoverable as one shared codec-stable covariance subspace in the
current period-8 LMS representation.

A local phase-cancellation probe then computed the spectrum of every spatial
block before averaging magnitudes across the image. Of 18 validation-screened
variants, period-8 unit-normalized block log-magnitude accepted 8 of 158 locked-
test OpenAI rows and zero of 135 controls, followed by 3 of 40 fresh OpenAI rows
and zero of 53 fresh controls. The fresh hits were complementary to the frozen
global eight-direction model, but neither OpenAI-oracle-positive image crossed
the new thresholds.

The broader provider distribution identifies the feature as another renderer
component. It accepted 17 of 603 explicit OpenAI-SynthID rows, 5 of 80 OpenAI-
lineage rows without an assertion, zero of 443 Google rows, and 2 of 112 other-
provider rows, both from Microsoft. An explicit assertion was not enriched over
same-lineage non-assertion (`p = 0.966`, one-sided exact test in the required
direction). Raising the frozen native and JPEG thresholds above the 32 same-
lineage validation maxima left zero of 158 locked-test positives. The feature
is independent of the fixed phase score but is not independently attributable
to SynthID.

An OpenAI-specific DTCWT screen then tested the shift-tolerant directional
wavelet proposal. It compared all six orientations, grouped diagonal and axis-
near bands, individual levels, and complex, magnitude, and phase statistics in
the period-8 cube-root-LMS residual. Validation selected all-orientation complex
correlation at 19 of 140 OpenAI rows and zero of 145 controls. The locked test
accepted 16 of 158 OpenAI rows and zero of 135 controls; the fresh holdout
accepted 2 of 40 OpenAI rows and zero of 53 controls.

The result strengthens the existing carrier attribution without supplying a
new decoder. Both fresh hits were already global phase hits, neither oracle-
positive image passed both thresholds, and 72 of 77 provider-challenge hits
overlapped the signed phase expert. The provider counts were 77 of 603 explicit
OpenAI-SynthID rows, 3 of 80 same-lineage non-assertions, zero of 443 Google
rows, and 2 of 112 other rows, both Microsoft. Assertion enrichment was
significant (`p = 0.00879`), but the union improved the phase expert only from
115 to 120 explicit rows. Calibration above the same-lineage validation maxima
left 4 of 158 locked-test and 1 of 40 fresh OpenAI rows, plus one Microsoft
test hit.

Most importantly, the frozen DTCWT decision was not shift invariant. One-pixel
and `(3, 5)` cyclic shifts, a 0.75x resize round trip, and a 5% crop round trip
all retained zero of 16 baseline detections. JPEG-90 retained four; WebP-95
retained 15 but accepted 25 OpenAI rows in total and introduced one of 135
controls. The wavelet representation is a more codec-tolerant view of the same
fixed raster phase, not a universal resolution or payload expert.

Family-wise selection did not uncover a shift-invariant exception. The best
magnitude candidate retained 10 of 158 locked-test OpenAI rows and zero of 135
controls, then 3 of 40 fresh OpenAI rows and zero of 53 controls; every fresh
hit was already a signed-phase hit. One-pixel and `(3, 5)` rolls, resize, and
crop each retained zero of the ten baseline magnitude detections. JPEG-90 kept
one and WebP-95 kept two. The best phase-only candidate failed the fresh test at
1 of 40 OpenAI rows versus 3 of 50 controls. Magnitude computed after periodic
complex folding still inherits the fixed phase origin and is not the intended
translation-insensitive DTCWT statistic.

Removing periodic folding altogether produced the intended translation-
insensitive statistic but lost discrimination. Nine global six-orientation,
three-level energy summaries selected median magnitude proportions within each
level on validation. The locked test accepted 5 of 158 OpenAI rows and 1 of 135
controls, and the fresh holdout accepted zero of 40 OpenAI rows and zero of 53
controls. In the measured representation, retaining the carrier also retains
its raster origin; pooling away that origin removes the transferable signal.

The 77 DTCWT provider-challenge hits were not a single temporal or geometric
rollout. Restricting both labels to `OpenAI Media Service API` gave 75/581
asserted hits versus 1/52 same-generator rows without an assertion. Asserted
rates stayed at 3/16, 46/365, and 26/200 from May through July and at 6/47,
44/320, and 25/214 over the three native geometries. The continuous
native/JPEG minimum score had 0.721 AUC between those two strata. This supports
a persistent but weak OpenAI component, not one obsolete encoder cohort;
non-assertion is still not an oracle-negative label.

Discarding absolute phase did not recover the missing variants. One
prespecified model sorted all 64 cyclic period-8 template correlations for
each image, fitted the resulting orbit shape on train only, and calibrated
native and JPEG-95 thresholds above all 145 validation controls. The two views
individually retained 5 and 7 of 140 validation positives, but their locked
conjunction accepted 0/158 OpenAI rows and 0/135 controls. The OpenAI evidence
that transfers is therefore signed raster phase; a generic shift-invariant
matched-filter shape is insufficient.

Three additional rescue families also failed. The official InvisMark decoder
checkpoint first passed its own watermark self-test at 0.997 confidence and
0.97 bit accuracy, but OpenAI hits, OpenAI misses, Google, Microsoft, Canva, and
same-provider controls all clustered near 0.18 confidence. It cannot veto
generic renderer matches. Applying DTCWT modulus before period folding retained
5 of 158 locked-test OpenAI rows and zero of 135 controls, then none of 40 fresh
OpenAI rows. A 16-codeword whitened period-8 model retained 5 of 158 and zero
controls, then 1 of 40 fresh OpenAI rows and 1 of 50 fresh controls. Neither
branch recovers the known oracle-positive miss or supports runtime routing.

The same content-hash audit found repeated uploads in every fresh temporal
report. Unique-group counts were 417 OpenAI positives rather than 486 rows and
211 Google positives rather than 234 rows. The conclusions were unchanged:
the signed OpenAI period-8 candidate accepted 4 of 417 unique positives and 1
of 454 general-control groups, the OpenAI full-image noiseprint accepted 68 of
417, and the Google runtime detector accepted 153 of 211 unique positives.

A previously prepared image-level patch-bag hypothesis was then executed. It
aggregates the mean, standard deviation, minimum, and maximum of nine learned
embeddings from normalized high-pass luminance and opponent-color patches. The
validation-selected model accepted 285 of 1,280 OpenAI rows above every
validation control. Without changing its weights or threshold, it accepted 324
of 1,364 development-test rows, 3 of 1,373 difficult controls, and 1 of 2,000
COCO controls. The later August temporal challenge accepted 120 of 486 OpenAI
rows, 8 of 504 general controls, and 5 of 33 same-provider rows without a
watermark assertion. Assertion enrichment over that same-provider stratum was
not independently significant (`p = 0.151`, one-sided exact test). Content
grouping reduced those counts to 107 of 417, 4 of 453, and 4 of 30,
respectively. A JPEG-95 conjunction retained only 1 of 486
OpenAI rows and no controls. Its native hits did not overlap the frozen signed
period-8 temporal hits. The model therefore reveals a complementary OpenAI
export noiseprint, not a codec-robust or watermark-specific decoder, and does
not enter runtime.

### 3.3 Official OpenAI pixel verification

`remove-ai-watermarks verify-openai-synthid image.png
--acknowledge-upload` uses OpenAI's official Content Provenance API for the
OpenAI half of the production detector. This is not the weak local period-8
research expert and it does not use C2PA as a proxy.

Before making one request, the command strips AI provenance metadata into a
temporary PNG, JPEG, or WebP file and compares hashes of the decoded RGBA raster
before and after. It refuses the upload if any AI marker survived, if the format
or pixels changed, or if the sanitized file exceeds 50 MiB. It then reads
exactly one independent `type == "synthid"` response entry and ignores the C2PA
entry. The source is not modified. Tests deliberately cover C2PA-only positive
responses, pixel mutation, surviving metadata, malformed response shapes, and
documented access and rate-limit failures.

The default SDK client fixes a 120-second request timeout and disables
automatic retries. One explicit acknowledgement therefore cannot silently
transmit the sanitized raster more than once. Timeout and connection failures
are errors, and request logs omit source paths and decoded-pixel hashes.

A live 2026-08-14 web-verifier smoke used the same sanitization invariant. Two
metadata-stripped, pixel-identical OpenAI images at 1536 by 1024 and 1024 by
1536 both returned `SynthID detected` with `Content Credentials not detected`.
An oracle-positive Google SynthID image and a COCO photograph, sanitized through
the same path, both returned OpenAI `SynthID not detected` and no Content
Credentials. This directly validates pixel-only and provider-specific behavior
for the production design. Four files are only a functional smoke test, not a
false-positive calibration, and the credentialed SDK endpoint itself was not
called because no API key was available.

This backend is deliberately excluded from `identify`: verification uploads
the sanitized raster to OpenAI, the endpoint is not eligible for Zero Data
Retention, and explicit acknowledgement is required. It is suitable for
individual supported OpenAI provenance checks, not adaptive detector fitting or
removal search. The API documentation prohibits repeated queries for watermark
reverse engineering or evasion. As with every detector in this project,
`not_detected` is absence of recognized evidence, not proof of human authorship.

### 3.4 How our tool recognizes SynthID from provenance

We recognize SynthID indirectly from supported C2PA evidence; this is not a
pixel watermark decode. Google states that all media generated by its tools is
watermarked, so Google AI C2PA establishes SynthID. OpenAI C2PA predates its
SynthID rollout, but current manifests add the signed
`c2pa.watermarked.unbound` action; OpenAI provenance establishes SynthID only
when that action is present. Legacy OpenAI C2PA without it remains valid origin
evidence but does not assert a pixel watermark.

This works while the C2PA manifest is intact and is silent once the manifest is
stripped or the image is re-encoded without C2PA (e.g., a screenshot, a
social-media re-upload, or after `metadata --remove`).

This is why:
- `identify` on a GitHub-recompressed issue attachment returns Unknown (C2PA is
  gone) even though the pixel SynthID is still present and detectable by
  openai.com/verify.
- A quiet `identify` output is not proof that SynthID was removed -- it only
  means the metadata signal is gone.

### 3.5 Oracle scope: each vendor detects only their own

OpenAI's current Content Provenance API documentation says it checks supported
OpenAI signals and is not a general-purpose AI detector. Google's current Gemini
documentation likewise says Gemini recognizes SynthID from Google AI tools,
not other companies' payloads.

SynthID technology is used by multiple vendors, but each verifier is keyed to
its own payload:

| Oracle | Detects | Does not detect |
| --- | --- | --- |
| Gemini app verification | Google SynthID | OpenAI SynthID |
| OpenAI Content Provenance API or web verifier | Supported OpenAI SynthID | Google SynthID |

A Google-SynthID image reads clean on openai.com/verify. An OpenAI image reads
clean in the Gemini oracle. They are different payloads within the same
framework.

### 3.6 Video verification and attack harness

Gemini's built-in verification flow reports whether and where it detects Google
SynthID in a video. This remains a proprietary oracle: invoke `@synthid`, use
the supported content-verification question, and keep every file in a separate
new chat. A normal Gemini answer that discusses visual clues or metadata is not
an oracle verdict. Nor is an adversarial follow-up that asks the chat model to
ignore and reinterpret a completed verifier result.

The research harness `scripts/video_synthid_sweep.py` tests a VAE regeneration
attack without pretending to detect success locally. It emits:

1. a re-encode control using the same sampled frames, dimensions, frame rate,
   and codec as the candidates;
2. VAE round-trip candidates with one spatial latent-noise field shared across
   time;
3. paired PSNR and motion-compensated temporal-residual metrics;
4. an empty oracle column for the external verdict.

The control is the first oracle submission. If it is not SynthID-positive, stop:
the surrounding transcode already changed the verifier result. Only a
control-positive, candidate-negative pair is evidence about the regeneration
attack. PSNR and temporal residual measure fidelity and flicker, never watermark
presence.

The shipped `video invisible` command and `remove_video_invisible` API reuse the
same VAE regeneration mechanism for a complete input sequence. The shipped
default is oracle-certified and does not expose a separate verification-status
flag. In the 2026-07-29
two-carrier calibration, both matched controls were positive in the built-in
verifier; the stronger candidate was negative on both, while a weaker
candidate was negative on one. A 2026-07-30 `UNAVAILABLE` response came from an
ordinary-model follow-up that asked Gemini to reinterpret the already returned
verdict and therefore did not invalidate it. The default is a calibrated,
content-dependent operating point. A per-file provider check remains an
optional audit after provider changes or for unusually important files.

The 2026-07-31 full-clip calibration used Google's public eight-second Veo
off-road sample through the complete product command. The original was detected
across 00:00-00:07, the `noise_std=0.10` output remained detected, and the
`0.15` output was not detected. The positive `0.10` result proves that the
surrounding 512 px / 12 fps / H.264 path did not create the negative result by
itself. `0.15` is therefore the shipped default. The tracked manifest
`data/evaluations/video-synthid-oracle.csv` records the public source URL,
hashes, fidelity metrics, and verdicts without committing generated videos.

What that calibration does and does not constrain, the ranked experiment program
for trading less quality for the same removal, and the change candidates that were
refuted along the way are recorded in
[`video-synthid-quality-research.md`](video-synthid-quality-research.md).

The VAE perturbation follows the general regeneration-attack construction from
Zhao et al. The video-specific control and temporal metric are local additions.
VideoMarkBench motivates testing frame aggregation and matched perturbations,
but it does not evaluate Google's proprietary SynthID, so its findings cannot
stand in for the Gemini oracle.

---

## 4. Adoption and current state (as of June 2026)

### 4.1 Google products

Google has watermarked **over 10 billion** images and video frames. The
deployment split by surface matters for our tool:

| Surface                              | SynthID pixel | C2PA metadata | Visible sparkle |
|--------------------------------------|---------------|---------------|-----------------|
| Gemini app (generated images)        | YES           | YES (Google)  | YES             |
| Gemini API / AI Studio / Nano Banana | YES           | NO            | YES             |

The Gemini API surface is a key blind spot: it embeds the pixel watermark and
the visible sparkle but **no C2PA or IPTC at all**. Our `identify` returns
Unknown on API-generated images unless the visible sparkle is detected (via
`check_visible=True`) or the user runs the Gemini app oracle.

### 4.2 OpenAI

OpenAI confirmed SynthID adoption (Help Center, updated 2026-05-21):

> "ChatGPT images include both C2PA metadata and SynthID watermarks."

This is time-gated: pre-rollout ChatGPT/gpt-image images carry C2PA without
SynthID. Current OpenAI manifests distinguish the watermarked output with the
signed `c2pa.watermarked.unbound` action. The detector requires that action, so
old OpenAI C2PA remains an origin signal without becoming a SynthID claim.

### 4.3 Other vendors

- **Kakao** (South Korea): SynthID adopter as of May 2026 (Google announcement)
- **NVIDIA Cosmos**: SynthID for video (not still images; different pipeline)
- **Meta AI**: does NOT use SynthID; uses IPTC `digitalSourceType` marker instead

### 4.4 Version evolution (v1 vs v2 hardening)

Google has not publicly documented version numbers for the SynthID image
watermark in a way that maps to our testing observations. What is known
empirically from oracle tests:

- **Before May 2026 (Gemini)**: strength 0.05 removed the watermark
- **May 2026 (Gemini)**: strength 0.05 insufficient; 0.10 required
- **Current (Gemini, June 2026)**: on the capped 1536 path, 0.05 and 0.10 do
  NOT clear; 0.15 clears (n=4, Gemini app oracle). See section 2.2.
- **OpenAI (June 2026)**: clears at 0.05 across 1024-1600 (n=4, clean v0.8.6).
  The earlier "0.30 still detected on 1600x1600" report (issue #14) was the
  text-protection bug, not a hardening of the watermark -- see the correction in
  section 2.2.

Google has hardened SynthID relative to OpenAI's (vendor gap measured at ~3x
strength), but the year-over-year "0.05 -> 0.10 -> 0.30" progression above
conflates a real hardening trend with the now-debunked region-rescrub artifact;
treat only the section 2.2 controlled numbers as authoritative.

---

## 5. Practical implications for this tool

### 5.1 Preserving content means regenerating it, never copying it

**Core rule:** SynthID is a pixel-amplitude pattern, so any approach that FREEZES
or RESTORES original pixels in a region re-introduces the watermark there. Early
region-based text/face "protection" (since removed) proved this: restoring the
original face pixels guaranteed SynthID survived in faces, and even a per-region
high-resolution re-scrub from an upscaled crop could be insufficient to destroy
the payload, reconstituting SynthID in text. The lesson held and shaped the
current design: **content is preserved by REGENERATING it under structural
conditioning, never by copying original pixels.**

> **Superseded in 0.24.0.** The `controlnet`, `sdxl`, `qwen` and `default` profiles
> were removed, and a retired name is now rejected at parse time rather than routed
> onward. `--pipeline` accepts only `qwen-zimage` (the default) and `sdxl-zimage`;
> both are CUDA-only, both condition their global stage on a canny edge map, and both
> run the same Z-Image face stage. The bullets below are a record of what was measured
> on the removed profiles, kept because the oracle verdicts are still the evidence the
> current design rests on.

- **Text + structure:** `--pipeline controlnet` (SDXL img2img + a canny ControlNet) is
  **THE DEFAULT pipeline since 2026-06-09** (`--pipeline default` opts down to plain
  SDXL img2img for inputs without text/faces). It conditions the regeneration on the
  edge map, so text and structure stay sharp while every pixel is still regenerated. Text legibility is
  better than plain img2img at the same strength (text stays readable where plain
  garbles it). **BUT removal efficacy at the low vendor-adaptive strength is CONTENT ×
  PIPELINE dependent and NEITHER pipeline clears all content -- oracle-validated
  2026-06-04 (8 OpenAI images, strength 0.10/0.15, max-res 1536).** The survivors FLIP
  by content type: **photoreal** (a 9-face grid, a bracelet product photo) SURVIVES
  controlnet but CLEARS `default`; **flat graphic** (a logo/poster with large flat
  color fills) SURVIVES `default` but CLEARS controlnet; a flat **text** card cleared
  under both. Why: controlnet's dense edge map keeps the regen too close to the
  original on photoreal (so SynthID survives) but freely repaints flat fills (so it
  clears them); plain img2img at low strength perturbs photoreal texture enough but
  barely touches flat fills. **Root cause = insufficient STRENGTH, not the pipeline:
  the vendor-adaptive 0.10 is NOT universally sufficient (the June numbers below held
  for the content they were measured on). The robust fix is a HIGHER strength,
  oracle-revalidated per content type (controlnet can be cranked harder without losing
  structure; a lower `controlnet_conditioning_scale` also frees the regen on
  photoreal).** So neither `--pipeline controlnet` nor plain `default` is a drop-in
  removal guarantee at today's strength -- pick by what you must PRESERVE (controlnet
  for text/structure), then raise strength until the oracle reads clean. (The earlier
  "reads clean on the oracle" claim held only for the one flat/text-background case it
  was checked on; it does not generalize.) **UPDATE 2026-06-09: the default strengths
  were raised and made pipeline-aware (controlnet ladder = the certified
  0.20/0.30/0.30 floors, applied to BOTH pipelines as a single ladder -- see §5.2 for
  why one ladder covers plain `sdxl` too) and controlnet is now the default pipeline.
  The plain-SDXL profile was also renamed `default` -> `sdxl` (`default` stays as an
  alias). The 0.10/0.15 numbers in this analysis are the PRE-raise values it was
  measured at. See §5.2.**
- **Highest-fidelity CUDA option:** `--pipeline qwen-zimage` is the recommended
  quality mode when preserving face identity matters more than latency, model size,
  and GPU cost. ControlNet was then the default, because it was much cheaper and ran on
  CUDA, XPU, MPS, and CPU, but canny conditioning preserves edges rather than identity.
  On two direct upstream comparisons, `qwen-zimage` retained substantially more
  ArcFace identity than polished ControlNet. On 2026-07-25 the exact six-output
  `visible -> qwen-zimage -> metadata` candidate was negative in the corresponding
  OpenAI and Gemini oracles. This is a quality recommendation for the measured content,
  not broad removal certification; very small text can still degrade.
  See `docs/qwen-improvement-research.md` for the identity and text metrics and the
  validation scope of those comparisons.
- **Face identity:** canny holds face *structure* but not *identity*. The removed
  SDXL and ControlNet profiles did not run a separate face-restoration stage, and
  earlier GFPGAN, PhotoMaker, and FaceID experiments were dropped after they
  degraded identity or risked reintroducing source pixels. Both shipped profiles
  now run the same face-specific stage: YuNet and SAM locate faces, then Z-Image
  regenerates the selected original face crops before a feathered composite. See
  `docs/controlnet-removal-pipeline-research.md` for the historical experiments.

### 5.2 Strength setting

There is no single permanent correct strength, but the controlled June 2026
study (section 2.2) gives empirical floors:

- **OpenAI**: 0.05 clears across 1024-1600 (n=4) -- **but content-dependent, NOT
  universal.** The follow-up oracle pass (2026-06-04, 8 images) found a flat-graphic
  OpenAI logo/poster still SynthID-detected after `default` at 0.10, and photoreal
  images still detected after controlnet at 0.10/0.15: at low strength the
  low-change regions (large flat fills under `default`, dense edges under controlnet)
  are not perturbed enough. So the 0.05 floor held only for the n=4 content it was
  measured on; treat it as a lower bound, not a guarantee, and raise + oracle-recheck
  per content type (see §5.1 controlnet bullet).
- **Google (capped 1536)**: 0.15 (n=4); 0.05 and 0.10 do not clear.
- **Google native 2816**: 0.15 clears (n=2, deployed controlnet worker, 2026-06-14) --
  the same rung as capped 1536, so no resolution penalty was observed.

> **Superseded in 0.24.0.** The `sdxl`, `controlnet`, `qwen` and `default` profiles
> were removed, and `OPENAI_STRENGTH` / `GEMINI_STRENGTH` / `UNKNOWN_STRENGTH` went
> with them. Everything from here to the end of this section is a record of what was
> measured on those profiles, kept because the oracle verdicts are still the evidence
> base. For the strength policy in force now see `module-internals.md`: `qwen-zimage`
> uses `resolution_adaptive_denoise`, `sdxl-zimage` a flat vendor ladder.

The default was **vendor-adaptive** (`watermark_profiles.resolve_strength` +
`vendor_for_strength`): the tool read the C2PA issuer on the original input and picked
`OPENAI_STRENGTH` 0.10 / `GEMINI_STRENGTH` 0.15 / `UNKNOWN_STRENGTH` 0.15 **(LOWERED
2026-06-14 from the 2026-06-04 cert floors 0.20/0.30/0.30)**. **The SAME ladder applied
to both pipelines** (`sdxl` and `controlnet`). The 2026-06-14 re-test on the deployed
Modal controlnet worker (v0.10.0) cleared SynthID on the oracle at OpenAI 0.10 (2
photoreal) and Google 0.15 (2 NATIVE 2816x1536, contradicting the "native >= 0.30" guess
on line above), and a pixel sweep showed 0.20/0.30 over-regenerated for no efficacy gain.
**This re-opens a genuine tension with the 2026-06-04 pass, which found photoreal STILL
detected after controlnet at 0.10/0.15 (lines above):** either the v0.10.0 controlnet
default improved the floor, or n=2 landed on the lucky side of the seed-non-determinism
(§5.5). So a SERVICE on this ladder MUST pin a fixed, oracle-verified seed (not random),
and flat-graphic hard cases (NOT in the n=2 re-test) still need a per-content oracle
recheck -- raise `--strength` there. The prior cert floors are the §5.5 record. Why one ladder
covers plain `sdxl` too: the certification was run on controlnet and does NOT transfer
by symmetry (the two pipelines have OPPOSITE hard cases -- controlnet leaves SynthID on
photoreal, `sdxl` on flat graphics, the §5.1 content-x-pipeline table), BUT on its own
hard case (flat fills) `sdxl` is the WEAKER remover (plain img2img barely perturbs a
flat region at low strength), so it needs AT LEAST controlnet's strength -- the
certified floor is therefore the right floor for `sdxl` too. This is a MARGIN argument
for `sdxl`, not a separate certification (the tested geometries are outside the
current local detector's scope).
The higher strength costs little quality where it matters, because `controlnet` is now
the default pipeline, so `sdxl` is reached only via an explicit `--pipeline sdxl` (a
deliberate opt-down), where over-regeneration has no faces/text to damage.
This uses the vendor signal we DO have locally (the C2PA SynthID provenance) to avoid the
overkill of a single high default on OpenAI images, without needing a local pixel
detector. An explicit `--strength` always wins. If the watermark still survives (e.g. a
large native Gemini beyond the capped-1536 validation), raise toward 0.35-0.40 (0.40
visibly corrupts dense text), using the lowest value that reads clean on the oracle.

**qwen-zimage global denoise, Gemini boundary bracketed (2026-08-02).** The profile does
not use the vendor ladder above; `resolution_adaptive_denoise` maps megapixels onto
roughly 0.084 (sub-0.3 MP) to 0.154 (>= 3.7 MP). A ladder on one native 2816x1536 Gemini
original, seed 0, everything else at profile defaults, verified through the Gemini app:

| global denoise | Gemini app | whole-image PSNR | face-box PSNR | edge IoU |
|---|---|---|---|---|
| 0.154 (profile top) | clean | 24.72 | 31.19 | 0.188 |
| 0.12 | clean | 25.65 | 31.82 | 0.202 |
| 0.10 | **clean** | 26.26 | 32.17 | 0.212 |
| 0.08 | **SynthID FOUND** | 26.95 | 32.51 | 0.227 |

So the boundary sits between 0.08 and 0.10 for this image, and the profile's shipped
0.154 carries roughly half a rung more strength than that content needed. Fidelity rises
monotonically all the way down - dropping to 0.10 buys **+1.54 dB whole-image and
+0.98 dB inside the face boxes** - which is exactly why the temptation is to move the
ceiling, and exactly why one fixture is not enough to do it.

Two constraints on reading this:

- **It brackets, it does not calibrate.** One image, one seed. Shipping the lowest clean
  rung means shipping at the measured cliff edge; another sample, seed, or content class
  can sit on the other side of it. Note §5.2's flat-graphic hard cases were not in this
  set at all.
- **The bottom of the curve was the untested end. It has now been measured, and it
  holds.** Every Gemini oracle fixture is 2816x1536, so the Google-side certification
  only ever covered 0.154, while `resolution_adaptive_denoise` sends sub-1 MP images to
  0.084-0.094 - at or below the rung that failed at 4.33 MP. Downscaling a Gemini
  original (valid test material: SynthID survives it by design) and running the deployed
  worker on it gives, through the Gemini app:

  | processing size | profile denoise | Gemini app |
  |---|---|---|
  | 1024x559 (0.57 MP) | 0.0896 | clean |
  | 1600x873 (1.40 MP) | 0.1066 | clean |

  So production's own low end clears Google, and the "small images are under-processed"
  failure mode is ruled out at these two sizes. **Read this as validation of the shipped
  curve, not as proof that the boundary moves with resolution.** 0.0896 sits inside the
  untested gap at 4.33 MP, where only 0.08 (found) and 0.10 (clean) were probed, so it
  may well clear at both sizes. The direction of any resolution dependence remains
  unproven (§5.5). Also note these are downscales of a 2816x1536 original rather than
  natively small Gemini outputs, which have still never been tested.

### 5.3 Test methodology

- **GitHub-recompressed JPEGs from issue attachments are valid SynthID test
  subjects.** JPEG re-encoding removes C2PA metadata but does NOT remove the
  SynthID pixel watermark (verified June 2026 on issue #14 pic3). Do not
  dismiss these as "not faithful originals" for SynthID-removal tests.
- **The correct oracle for OpenAI images is an authorized OpenAI provenance
  verifier**, not the Gemini app. OpenAI now documents both a web tool and a
  Content Provenance API; the API's published use restrictions still apply.
  The OpenAI and Google oracles detect different payloads.
- **A quiet `identify` output after processing is not proof of removal.** It
  means the provenance evidence is gone. The pixel watermark state is unknown without
  an oracle check.
- **After removal, the output may carry forensic artifacts** detectable by an
  independent classifier even if the vendor oracle reads negative. Defeating the
  verifier is not the same as being forensically indistinguishable from clean
  content (arXiv:2605.09203).

### 5.4 Strength vs forensic detectability: the tradeoff

Higher img2img strength removes the watermark but introduces detectable
regeneration artifacts. The Goonatilake & Ateniese paper shows the strongest
diffusion-based removers are simultaneously the most forensically detectable
(AUROC up to 0.9999). The tradeoff is unavoidable with current diffusion-based
approaches: defeating the vendor's verifier is not the same as being clean.

### 5.5 Oracle validation log -- 2026-06-04 OpenAI pass

Eight OpenAI `gpt-image` originals run through both pipelines and checked on
openai.com/verify (the OpenAI SynthID oracle). `--max-resolution 1536`; strength
is the vendor-adaptive default (`vendor_for_strength`): images with an OpenAI C2PA
manifest get `OPENAI_STRENGTH` 0.10, the one without C2PA falls to
`UNKNOWN_STRENGTH` 0.15. "detected" = SynthID still found (removal FAILED);
"clean" = SynthID not detected.

| image | content type | size | strength | `--auto`/controlnet | `default` |
|---|---|---|---|---|---|
| typography card | flat text | 1122x1402 | 0.10 | clean | clean |
| Flat poster | flat graphic (logo + flat fills) | 1024x1536 | 0.10 | clean | **detected** |
| 9-face grid | photoreal | 1448x1086 | 0.10 | **detected** | clean |
| bracelet product photo | photoreal | 1600x1600 | 0.15 | **detected** | clean |

(The other four cleared under both and are omitted.) **Reading:** at this strength
NEITHER pipeline removes SynthID on all content -- the survivors flip by content
type. Photoreal survives controlnet / clears `default`; flat graphic survives
`default` / clears controlnet; flat text clears both.

**Follow-up: removal near the threshold is NON-DETERMINISTIC (seed-dependent).**
Re-running the two photoreal survivors through controlnet at an explicit
`--strength 0.15` (`--auto`, same `--max-resolution 1536`) cleared BOTH on the
oracle (SynthID not detected). But the bracelet had SURVIVED controlnet at the
SAME 0.15 in the first pass (it was the no-C2PA image, so its vendor-adaptive
strength was already 0.15) -- same pipeline + strength + resolution, only the
random (unset) seed differed between runs. So **0.15 is the borderline floor for
controlnet photoreal, not a robust guarantee**: at the threshold the same
image+settings can pass or fail run-to-run. img2img runs with `seed=None` (random)
unless `--seed` is passed, so a removal SERVICE gets a coin-flip near threshold and
has no applicable local SynthID detector at these geometries to self-verify.

**Controlnet strength ladder on the two photoreal images (oracle, `--auto`,
`--max-resolution 1536`):**

| controlnet strength | 9-face grid | bracelet photo |
|---|---|---|
| 0.10 | detected | (was 0.15) |
| 0.15 | clean | **non-deterministic** (survived pass 1, clean pass 2) |
| **0.20** | **clean** | **clean** |

**Recommended robust controlnet strength = 0.20** (0.05 of margin above the 0.15
non-deterministic borderline); both photoreal survivors cleared at 0.20. Honest
caveat: 0.20 is one confirming run WITH margin, not an N-run repeatability proof --
for a removal service, add a little more margin or validate repeatability, since
these geometries are outside the current local detector's scope. **Implications:** (1) the
content×pipeline table above conflates a borderline/non-deterministic 0.15 result
with deterministic content behavior -- the photoreal-survives-controlnet effect is
solid at 0.10 but at 0.15 it is near-threshold noise; (2) for reliable removal pick
a strength with MARGIN above the borderline (controlnet >= 0.20), not exactly on
it; (3) **historical engineering conclusion:** this dated run argued for a
higher ControlNet strength than the then-current default. That proposal was
later superseded. The current resolver intentionally shares the 0.10/0.15
ladder between SDXL and ControlNet and uses a separate Qwen ladder; see
`_internal/watermark_profiles.py`.
Source images are private (faces / product shots), not committed; reproduce on any
photoreal + flat-graphic gpt-image pair, varying the seed, and re-checking the
oracle.

**Gemini pass + the face-restore re-introduction (2026-06-04).** Four Gemini
originals via the then-current `--auto` ControlNet path at `--max-resolution 1024`,
checked on the
Gemini "Verify with SynthID" oracle (Google content needs the Google oracle, not
openai.com/verify):
- Most cleared at controlnet 0.15-0.25; `gemini_3` (a large central FACE, +restore)
  stayed **SynthID-detected at controlnet 0.15, 0.20 AND 0.25** -- raising strength
  did not crack it.
- **Root cause was the face-restore pass, not strength/resolution.** `gemini_3` at
  controlnet 0.20 with `--no-restore-faces` read **SynthID-NOT-detected** (clean
  A/B, only restore differed). GFPGAN runs on the ORIGINAL watermarked face and at
  weight 0.5 blends ~half its pixels back, re-introducing SynthID into the
  composited face over the diffusion-cleaned result (see §5.1 face-identity bullet).
- (Side note: reducing the processing resolution does NOT weaken SynthID -- it is
  robust to downscaling by design, so 1024 was never the wall. Whether a lower
  processing resolution then needs more or less removal strength is NOT established;
  see the note below.)

**Historical controlnet certification, superseded by the current vendor-adaptive
defaults (isolated GPU sweep + oracle,
restore OFF, <= 1536, each vendor on its own oracle):** OpenAI **0.20** (2 photoreal x
seed {1,2,3} = 6/6 clean; the 0.15-flipper is seed-robust at 0.20) and Gemini **0.30**
(0.20 detected -> 0.30 clean on 2/2 seeds). Both were measured at <= 1536 only. See
`docs/controlnet-removal-pipeline-research.md` for the table.

**Whether Gemini removal is resolution-sensitive is UNPROVEN, in either direction.**
This document previously asserted it was, and recommended capping Gemini at 1536 with
0.30 or "native-calibrating" to ~0.35+. Nothing measured that. The one relevant
measurement points the other way: the 2026-06-14 deployed-worker re-test cleared Gemini
at **0.15 on two NATIVE 2816x1536 images**, the same rung as capped 1536. So there is no
observed native-resolution penalty, and no observed benefit either -- the low-resolution
end has simply never been through the Gemini oracle on any pipeline. Do not reason from
a resolution trend here; measure it.

**Current implication:** the old floor table remains evidence about the dated
test set, not the current resolver. The SDXL and ControlNet profiles it measured
no longer exist; the shipped defaults are defined in `watermark_profiles.py`, and
both surviving profiles run face repair as a built-in second stage rather than as
an optional restore. Removal near a threshold remains seed dependent, so
reproducible verification requires a fixed seed.

---

## References

1. Gowal et al. (2025). **SynthID-Image: Image watermarking at internet scale.**
   arXiv:2510.09263. https://arxiv.org/abs/2510.09263

2. Google DeepMind. **Identifying AI-generated images with SynthID.** Blog post,
   2023. https://deepmind.google/blog/identifying-ai-generated-images-with-synthid/

3. Google DeepMind. **SynthID.** Product page.
   https://deepmind.google/models/synthid/

4. Goonatilake & Ateniese (2026). **Removing the Watermark Is Not Enough:
   Forensic Stealth in Generative-AI Watermark Removal.** arXiv:2605.09203.
   https://arxiv.org/abs/2605.09203

5. OpenAI. **Content provenance.**
   https://developers.openai.com/api/docs/guides/content-provenance

6. Google. **Verify AI-generated images, videos, and audio.**
   https://support.google.com/gemini/answer/16722517

7. Zhao et al. (2024). **Invisible Image Watermarks Are Provably Removable
   Using Generative AI.** NeurIPS 2024, arXiv:2306.01953.
   https://arxiv.org/abs/2306.01953

8. Jiang et al. (2025). **VideoMarkBench: Benchmarking Robustness of Video
   Watermarking.** arXiv:2505.21620.
   https://arxiv.org/abs/2505.21620

9. OpenAI. **ChatGPT Images 2.0 system card.**
   https://deploymentsafety.openai.com/chatgpt-images-2-0/automated-evaluations-and-adversarial-testing

10. Cao et al. (2026). **MarkNull: Model-Agnostic Watermark Removal in
    AI-Generated Images via On-Manifold Latent Manipulation.** USENIX Security
    2026, arXiv:2608.10166. https://arxiv.org/abs/2608.10166
